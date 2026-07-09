from __future__ import annotations

import io
import logging
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import get_db
from app.connectors.base import ManualOnlyError
from app.connectors.sync import sync_account
from app.db import SessionLocal
from app.scheduler.batch import run_batch, BatchConfig
from app.scheduler.runs import BATCH_RUNS, new_run_id, record_run, start_batch

logger = logging.getLogger(__name__)
from app.ingest.manual_import import import_snapshots_csv
from app.loop.engine import run_loop
from app.api.overview import build_overview
from app.models import Account, AccountSegment, AudienceSegment, ChannelBrief, ContentItem, Draft, Endpoint, Evaluation, LoopRun, PublishDispatch, Recommendation, Snapshot, VideoAsset
from app.flow.build import build_flow
from app.flow.classify import classify_audience
from app.analysis.claude_client import ClaudeClient
from app.analysis.factory import resolve_llm_client
from app.analysis.script import generate_script
from app.config import settings
from app.video.factory import resolve_video_provider
from app.video.governor import generate_video, usage_summary, VideoConfig
from app.video.base import VideoQuotaExceeded, NearDuplicateScript
from app.connectors.aitoearn_client import AiToEarnClient
from app.connectors.linking import link_aitoearn_accounts
from app.analysis.performance import content_performance, performance_prompt_block
from app.orchestrator.state import is_paused, set_paused, flywheel_state

router = APIRouter()


def _latest(db: Session, model, account_id: int, *order):
    stmt = select(model).where(model.account_id == account_id).order_by(*order)
    return db.scalars(stmt).first()


def _list_item(db: Session, acc: Account,
               snap=None, ev=None, run=None) -> schemas.AccountListItem:
    # snap/ev/run are pre-fetched by list_accounts; single-account callers pass None → lazy fetch
    if snap is None:
        snap = _latest(db, Snapshot, acc.id, Snapshot.ts.desc(), Snapshot.id.desc())
    if ev is None:
        ev = _latest(db, Evaluation, acc.id, Evaluation.created_at.desc(), Evaluation.id.desc())
    if run is None:
        run = _latest(db, LoopRun, acc.id, LoopRun.ts.desc(), LoopRun.id.desc())
    return schemas.AccountListItem(
        id=acc.id,
        platform=acc.platform,
        handle=acc.handle,
        vertical=acc.vertical,
        positioning=acc.positioning,
        latest_followers=snap.followers if snap else None,
        latest_composite_score=ev.composite_score if ev else None,
        latest_loop_status=run.status if run else None,
        source_tier=snap.source_tier if snap else None,
    )


@router.post("/accounts", response_model=schemas.AccountListItem, status_code=201)
def create_account(payload: schemas.AccountCreate, db: Session = Depends(get_db)) -> schemas.AccountListItem:
    data = {k: v for k, v in payload.model_dump().items() if v is not None}  # creation only - None fields fall back to ORM defaults
    acc = Account(**data)
    db.add(acc)
    db.commit()
    return _list_item(db, acc)


@router.get("/accounts", response_model=list[schemas.AccountListItem])
def list_accounts(db: Session = Depends(get_db)) -> list[schemas.AccountListItem]:
    accounts = list(db.scalars(select(Account).order_by(Account.id)).all())

    # batch: latest snapshot/eval/loop per account (last write wins after ascending sort)
    latest_snap: dict[int, object] = {}
    for s in db.scalars(select(Snapshot).order_by(Snapshot.account_id, Snapshot.ts, Snapshot.id)).all():
        latest_snap[s.account_id] = s

    latest_ev: dict[int, object] = {}
    for e in db.scalars(select(Evaluation).order_by(Evaluation.account_id, Evaluation.created_at, Evaluation.id)).all():
        latest_ev[e.account_id] = e

    latest_run: dict[int, object] = {}
    for lr in db.scalars(select(LoopRun).order_by(LoopRun.account_id, LoopRun.ts, LoopRun.id)).all():
        latest_run[lr.account_id] = lr

    return [_list_item(db, a,
                       snap=latest_snap.get(a.id),
                       ev=latest_ev.get(a.id),
                       run=latest_run.get(a.id)) for a in accounts]


@router.get("/accounts/{account_id}", response_model=schemas.AccountDetail)
def get_account(account_id: int, db: Session = Depends(get_db)) -> Account:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return acc


@router.post("/import/snapshots")
def import_snapshots(payload: schemas.ImportSnapshotsIn, db: Session = Depends(get_db)) -> dict:
    try:
        return import_snapshots_csv(db, io.StringIO(payload.csv))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"CSV import failed: {exc}") from exc


@router.post("/accounts/{account_id}/loop", response_model=schemas.LoopRunOut)
def trigger_loop(account_id: int, db: Session = Depends(get_db)) -> LoopRun:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        return run_loop(db, acc, llm_client=resolve_llm_client())
    except Exception as exc:  # TODO(plan-8): categorise LLM vs data errors
        raise HTTPException(status_code=500, detail=f"loop run failed: {exc}") from exc


_REC_STATUSES = {"pending", "adopted", "rejected", "worked", "failed"}
_DRAFT_STATUSES = {"pending", "adopted", "rejected"}


@router.post("/recommendations/{rec_id}/status", response_model=schemas.RecommendationOut)
def set_recommendation_status(rec_id: int, payload: schemas.SetStatusIn, db: Session = Depends(get_db)) -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    status = payload.status
    if status not in _REC_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid status; allowed: {sorted(_REC_STATUSES)}")
    rec.status = status
    db.commit()
    return rec


@router.post("/drafts/{draft_id}/status", response_model=schemas.DraftOut)
def set_draft_status(draft_id: int, payload: schemas.SetReviewStatusIn, db: Session = Depends(get_db)) -> Draft:
    draft = db.get(Draft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    review = payload.review_status
    if review not in _DRAFT_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid review_status; allowed: {sorted(_DRAFT_STATUSES)}")
    draft.review_status = review
    db.commit()
    return draft


@router.post("/batch/run")
def batch_run(background_tasks: BackgroundTasks, sync: bool = True,
              max_accounts: int | None = None, background: bool = False,
              db: Session = Depends(get_db)) -> dict:
    cfg = BatchConfig(max_accounts=max_accounts)
    if background:
        run_id = new_run_id()
        record_run(run_id, {"status": "running", "report": None, "error": None})
        background_tasks.add_task(start_batch, run_id, SessionLocal, sync=sync, batch_cfg=cfg)
        return JSONResponse(status_code=202, content={"run_id": run_id, "status": "running"})
    report = run_batch(db, sync=sync, batch_cfg=cfg)
    return asdict(report)


@router.get("/batch/runs/{run_id}")
def batch_run_status(run_id: str) -> dict:
    entry = BATCH_RUNS.get(run_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, **entry}


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return build_overview(db)


@router.get("/content", response_model=list[schemas.ContentLibraryItem])
def content_library(platform: str | None = None, account_id: int | None = None,
                    limit: int = Query(default=200, ge=1, le=1000), db: Session = Depends(get_db)) -> list[schemas.ContentLibraryItem]:
    stmt = select(ContentItem, Account).join(Account, ContentItem.account_id == Account.id)
    if platform:
        stmt = stmt.where(Account.platform == platform)
    if account_id:
        stmt = stmt.where(ContentItem.account_id == account_id)
    # nulls-last sort: use boolean expression fallback for SQLite compatibility
    stmt = stmt.order_by(
        (ContentItem.views == None),  # noqa: E711 - SQLAlchemy equality, not is None
        ContentItem.views.desc(),
        ContentItem.id,
    ).limit(limit)
    rows = db.execute(stmt).all()
    return [
        schemas.ContentLibraryItem(
            id=ci.id, account_id=ci.account_id, account_handle=acc.handle, platform=acc.platform,
            topic=ci.topic, views=ci.views, likes=ci.likes, comments=ci.comments, published_at=ci.published_at,
        )
        for ci, acc in rows
    ]


@router.get("/flow")
def flow(db: Session = Depends(get_db)) -> dict:
    return build_flow(db)


@router.post("/segments", status_code=201)
def create_segment(payload: schemas.SegmentCreate, db: Session = Depends(get_db)) -> dict:
    seg = AudienceSegment(label=payload.label)
    db.add(seg)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="already exists")
    return {"id": seg.id, "label": seg.label}


@router.post("/endpoints", status_code=201)
def create_endpoint(payload: schemas.EndpointCreate, db: Session = Depends(get_db)) -> dict:
    ep = Endpoint(name=payload.name, url_pattern=payload.url_pattern)
    db.add(ep)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="already exists")
    return {"id": ep.id, "name": ep.name, "url_pattern": ep.url_pattern}


@router.get("/segments")
def list_segments(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AudienceSegment).order_by(AudienceSegment.label)).all()
    return [{"id": s.id, "label": s.label} for s in rows]


@router.get("/endpoints")
def list_endpoints(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Endpoint).order_by(Endpoint.name)).all()
    return [{"id": e.id, "name": e.name, "url_pattern": e.url_pattern} for e in rows]


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)) -> dict:
    from app.flow.demo import reset_flow
    return reset_flow(db)


@router.post("/accounts/{account_id}/segments")
def set_composition(account_id: int, payload: schemas.SetComposition, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    seen_ids: set[int] = set()
    for item in payload.segments:
        if item.segment_id in seen_ids:
            raise HTTPException(status_code=422, detail="duplicate segment_id in payload")
        seen_ids.add(item.segment_id)
    for item in payload.segments:
        if db.get(AudienceSegment, item.segment_id) is None:
            raise HTTPException(status_code=422, detail=f"segment {item.segment_id} not found")
    db.query(AccountSegment).filter_by(account_id=account_id).delete()
    for item in payload.segments:
        db.add(AccountSegment(account_id=account_id, segment_id=item.segment_id, weight=item.weight))
    db.commit()
    return {"account_id": account_id, "count": len(payload.segments)}


@router.post("/accounts/{account_id}/endpoint")
def set_endpoint(account_id: int, payload: schemas.SetEndpoint, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    if payload.endpoint_id is not None and db.get(Endpoint, payload.endpoint_id) is None:
        raise HTTPException(status_code=422, detail="endpoint not found")
    acc.endpoint_id = payload.endpoint_id
    db.commit()
    return {"account_id": account_id, "endpoint_id": acc.endpoint_id}


@router.post("/accounts/{account_id}/classify-audience")
def classify_audience_endpoint(account_id: int, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    all_segs = list(db.scalars(select(AudienceSegment)).all())
    labels = [s.label for s in all_segs]
    if not labels:
        raise HTTPException(status_code=422, detail="先创建人群标签(/segments)再归类")
    try:
        client = ClaudeClient()
    except Exception as exc:  # noqa: BLE001 - no key configured
        raise HTTPException(status_code=422, detail=f"LLM 未配置：{exc}") from exc
    content = list(db.scalars(select(ContentItem).where(ContentItem.account_id == account_id)).all())
    picked = classify_audience(acc, content, client, labels)
    seg_by_label = {s.label: s for s in all_segs}
    new_rows = [AccountSegment(account_id=account_id, segment_id=seg_by_label[lbl].id, weight=1.0) for lbl in picked]
    db.query(AccountSegment).filter_by(account_id=account_id).delete()
    db.add_all(new_rows)
    db.commit()
    return {"account_id": account_id, "segments": picked}


@router.post("/accounts/{account_id}/external-ref")
def set_external_ref(account_id: int, payload: schemas.SetExternalRef, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc.external_ref = payload.external_ref
    acc.external_source = payload.external_source
    db.commit()
    return {"account_id": account_id, "external_ref": acc.external_ref, "external_source": acc.external_source}


@router.post("/accounts/link-aitoearn")
def link_aitoearn(db: Session = Depends(get_db)) -> dict:
    if not (settings.aitoearn_base_url and settings.aitoearn_api_key):
        raise HTTPException(status_code=422, detail="AiToEarn 未配置(MATRIXLOOP_AITOEARN_BASE_URL/API_KEY)")
    client = AiToEarnClient(settings.aitoearn_base_url, settings.aitoearn_api_key)
    return link_aitoearn_accounts(db, client)


@router.post("/accounts/{account_id}/sync")
def sync_account_endpoint(account_id: int, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        return sync_account(db, acc)
    except ManualOnlyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector sync failed for account %s: %s", account_id, exc)
        raise HTTPException(status_code=502, detail="upstream connector error") from exc


@router.post("/accounts/{account_id}/brief")
def set_brief(account_id: int, payload: schemas.SetBrief, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account_id))
    if brief is None:
        brief = ChannelBrief(account_id=account_id, main_direction=payload.main_direction)
        db.add(brief)
    brief.main_direction = payload.main_direction
    brief.sub_niches = payload.sub_niches
    brief.tone = payload.tone
    brief.language = payload.language
    brief.persona = payload.persona
    brief.format = payload.format
    brief.compliance_stance = payload.compliance_stance
    db.commit()
    return {"account_id": account_id, "id": brief.id}


@router.get("/accounts/{account_id}/brief")
def get_brief(account_id: int, db: Session = Depends(get_db)) -> dict:
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account_id))
    if brief is None:
        raise HTTPException(status_code=404, detail="no brief for this account")
    return {
        "account_id": account_id, "id": brief.id, "main_direction": brief.main_direction,
        "sub_niches": brief.sub_niches, "tone": brief.tone, "language": brief.language,
        "persona": brief.persona, "format": brief.format, "compliance_stance": brief.compliance_stance,
    }


@router.post("/drafts/{draft_id}/generate-script", response_model=schemas.DraftOut, status_code=201)
def generate_script_route(draft_id: int, db: Session = Depends(get_db)) -> Draft:
    topic = db.get(Draft, draft_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="draft not found")
    if topic.kind != "topic":
        raise HTTPException(status_code=422, detail="draft must be of kind 'topic'")
    if topic.review_status != "adopted":
        raise HTTPException(status_code=422, detail="topic draft must be adopted first")
    client = resolve_llm_client()
    if client is None:
        raise HTTPException(status_code=422, detail="LLM 未配置(MATRIXLOOP_ANTHROPIC_API_KEY)")
    lr = db.get(LoopRun, topic.loop_run_id)
    if lr is None:
        raise HTTPException(status_code=422, detail="loop run not found")
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == lr.account_id))
    perf_block = performance_prompt_block(content_performance(db, lr.account_id))
    text = generate_script(topic.content, brief, client, performance=perf_block)
    script = Draft(loop_run_id=topic.loop_run_id, kind="script", content=text, review_status="pending")
    db.add(script)
    db.commit()
    return script


_VIDEO_REVIEW_STATUSES = {"pending", "approved", "rejected"}


@router.get("/video/usage")
def video_usage(db: Session = Depends(get_db)) -> dict:
    return usage_summary(db, cfg=VideoConfig())


@router.get("/video-assets", response_model=list[schemas.VideoAssetOut])
def list_video_assets(account_id: int | None = None, status: str | None = None,
                      review_status: str | None = None, db: Session = Depends(get_db)) -> list[VideoAsset]:
    stmt = select(VideoAsset).order_by(VideoAsset.id.desc())
    if account_id is not None:
        stmt = stmt.where(VideoAsset.account_id == account_id)
    if status is not None:
        stmt = stmt.where(VideoAsset.status == status)
    if review_status is not None:
        stmt = stmt.where(VideoAsset.review_status == review_status)
    return list(db.scalars(stmt).all())


@router.post("/video-assets/{asset_id}/status", response_model=schemas.VideoAssetOut)
def set_video_review(asset_id: int, payload: schemas.SetVideoReview, db: Session = Depends(get_db)) -> VideoAsset:
    asset = db.get(VideoAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    if payload.review_status not in _VIDEO_REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid review_status; allowed: {sorted(_VIDEO_REVIEW_STATUSES)}")
    asset.review_status = payload.review_status
    db.commit()
    return asset


@router.post("/accounts/{account_id}/generate-video", response_model=schemas.VideoAssetOut, status_code=201)
def generate_video_route(account_id: int, payload: schemas.GenerateVideoIn, db: Session = Depends(get_db)) -> VideoAsset:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    draft = db.get(Draft, payload.script_draft_id)
    if draft is None or draft.kind != "script":
        raise HTTPException(status_code=404, detail="script draft not found")
    try:
        return generate_video(db, acc, draft, provider=resolve_video_provider())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NearDuplicateScript as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def _aitoearn_client_or_422() -> AiToEarnClient:
    from app.config import settings
    if not (settings.aitoearn_base_url and settings.aitoearn_api_key):
        raise HTTPException(status_code=422, detail="AiToEarn 未配置(MATRIXLOOP_AITOEARN_BASE_URL/API_KEY)")
    return AiToEarnClient(settings.aitoearn_base_url, settings.aitoearn_api_key)


@router.post("/accounts/{account_id}/publish", response_model=schemas.PublishDispatchOut, status_code=201)
def publish_account(account_id: int, payload: schemas.PublishIn, db: Session = Depends(get_db)) -> PublishDispatch:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    asset = db.get(VideoAsset, payload.video_asset_id)
    if asset is None or asset.account_id != account_id:
        raise HTTPException(status_code=404, detail="video asset not found for this account")
    client = _aitoearn_client_or_422()
    from app.publish.dispatch import create_dispatch, PublishNotReady
    try:
        return create_dispatch(db, acc, asset, client=client, caption=payload.caption, publish_at=payload.publish_at)
    except PublishNotReady as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - upstream connector error
        db.rollback()
        logger.warning("publish failed for account %s: %s", account_id, exc)
        raise HTTPException(status_code=502, detail="upstream publish error") from exc


@router.get("/publish/dispatches", response_model=list[schemas.PublishDispatchOut])
def list_dispatches(account_id: int | None = None, db: Session = Depends(get_db)) -> list[PublishDispatch]:
    stmt = select(PublishDispatch).order_by(PublishDispatch.id.desc())
    if account_id is not None:
        stmt = stmt.where(PublishDispatch.account_id == account_id)
    return list(db.scalars(stmt).all())


@router.get("/publish/dispatches/{dispatch_id}", response_model=schemas.PublishDispatchOut)
def get_dispatch(dispatch_id: int, db: Session = Depends(get_db)) -> PublishDispatch:
    d = db.get(PublishDispatch, dispatch_id)
    if d is None:
        raise HTTPException(status_code=404, detail="dispatch not found")
    from app.publish.dispatch import refresh_dispatch
    try:
        client = _aitoearn_client_or_422()
    except HTTPException:
        return d   # AiToEarn not configured -> return stored state without polling
    return refresh_dispatch(db, d, client=client)


@router.post("/publish/refresh-analytics")
def refresh_publish_analytics(db: Session = Depends(get_db)) -> dict:
    client = _aitoearn_client_or_422()
    from app.publish.analytics import refresh_published_analytics
    return refresh_published_analytics(db, client=client)


@router.post("/accounts/{account_id}/autopilot")
def set_autopilot(account_id: int, payload: schemas.SetAutopilot, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc.autopilot = payload.enabled
    db.commit()
    return {"account_id": account_id, "autopilot": acc.autopilot}


@router.get("/flywheel/status")
def flywheel_status(db: Session = Depends(get_db)) -> dict:
    return {"paused": is_paused(db)}


@router.post("/flywheel/pause")
def flywheel_pause(db: Session = Depends(get_db)) -> dict:
    set_paused(db, True)
    return {"paused": True}


@router.post("/flywheel/resume")
def flywheel_resume(db: Session = Depends(get_db)) -> dict:
    set_paused(db, False)
    return {"paused": False}


@router.get("/flywheel")
def flywheel(db: Session = Depends(get_db)) -> dict:
    return flywheel_state(db)
