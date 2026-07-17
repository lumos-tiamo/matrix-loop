from __future__ import annotations

import io
import logging
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, tuple_
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
from app.models import Account, AccountSegment, AudienceSegment, Calibration, ChannelBrief, ContentItem, Draft, Endpoint, Evaluation, LoopRun, PublishDispatch, PublishPlan, Recommendation, Snapshot, Trend, VideoAsset
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
from app.analysis.trends import trend_prompt_block
from app.orchestrator.state import is_paused, set_paused, flywheel_state, flywheel_accounts, flywheel_events_since
from app.scheduler.control import start_scheduler, stop_scheduler, scheduler_running

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
    brief.target_seconds = payload.target_seconds
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
        "target_seconds": brief.target_seconds,
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
    trend_block = trend_prompt_block(db, brief.sub_niches) if brief else ""
    text = generate_script(topic.content, brief, client, performance=perf_block, trends=trend_block or None)
    script = Draft(loop_run_id=topic.loop_run_id, kind="script", content=text,
                   review_status="pending", parent_id=topic.id)
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


def _palmier_brand(acc, brief) -> dict:
    md = ((getattr(brief, "main_direction", "") if brief else "") or "").lower()
    color, accent = "#14331F", "#C6FF3A"  # default AI/科普
    for keys, c, a in (
        (("airdrop", "空投", "撸毛", "farm"), "#8B5CFF", "#C6FF3A"),
        (("trad", "charts", "chart", "技术", "交易", "ta"), "#12233F", "#38BDF8"),
        (("yield", "defi", "gold", "黄金", "理财", "收益", "rwa"), "#3A2A08", "#F5B301"),
    ):
        if any(k in md for k in keys):
            color, accent = c, a
            break
    name = (getattr(brief, "persona", None) if brief else None) \
        or (getattr(brief, "main_direction", None) if brief else None) \
        or (getattr(acc, "handle", None) if acc else None) or "Channel"
    return {"name": str(name)[:32], "color": color, "accent": accent,
            "handle": (getattr(acc, "handle", "") if acc else "")}


@router.get("/video-assets/{asset_id}/palmier-brief")
def palmier_brief(asset_id: int, db: Session = Depends(get_db)) -> dict:
    """Everything an agent needs to build/finish this asset in Palmier: the local source file,
    the narration script, per-channel brand config, and resolution."""
    import os
    from app.config import settings
    a = db.get(VideoAsset, asset_id)
    if a is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    fname = (a.media_url or "").rsplit("/", 1)[-1]
    vids = os.path.abspath(settings.video_output_dir)
    local = os.path.join(vids, fname) if fname else None
    script = db.get(Draft, a.script_draft_id) if a.script_draft_id else None
    acc = db.get(Account, a.account_id)
    brief = db.scalar(select(ChannelBrief).where(ChannelBrief.account_id == a.account_id))
    return {
        "asset_id": a.id, "status": a.status, "review_status": a.review_status,
        "media_url": a.media_url,
        "local_path": local if (local and os.path.exists(local)) else None,
        "script": script.content if script else None,
        "account": ({"platform": acc.platform, "handle": acc.handle, "vertical": acc.vertical} if acc else None),
        "brand": _palmier_brand(acc, brief),
        "resolution": [1080, 1920],
    }


@router.post("/video-assets/{asset_id}/finish", response_model=schemas.VideoAssetOut)
def palmier_finish(asset_id: int, payload: schemas.PalmierFinishIn, db: Session = Depends(get_db)) -> VideoAsset:
    """Register a Palmier-exported file as this asset's finished media (repoints media_url;
    copies the file into video_output_dir if it isn't already there)."""
    import os
    import shutil
    from app.config import settings
    a = db.get(VideoAsset, asset_id)
    if a is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    vids = os.path.abspath(settings.video_output_dir)
    fname = os.path.basename(payload.file_path)
    src = os.path.abspath(payload.file_path) if os.path.isabs(payload.file_path) else os.path.join(vids, fname)
    if not os.path.exists(src):
        raise HTTPException(status_code=422, detail=f"file not found: {src}")
    dst = os.path.join(vids, fname)
    if os.path.abspath(src) != dst:
        shutil.copy(src, dst)
    a.media_url = f"{settings.public_base_url}/media/{fname}"
    if "palmier" not in (a.provider or ""):
        a.provider = ((a.provider or "")[:24] + "+palmier")
    a.stage = "palmier_done"   # clear any queue marker
    db.commit()
    return a


@router.post("/video-assets/{asset_id}/queue-palmier", response_model=schemas.VideoAssetOut)
def queue_palmier(asset_id: int, db: Session = Depends(get_db)) -> VideoAsset:
    """Flag a ready asset for the Palmier finishing pass (the '送 Palmier 精修' button). The
    scheduled agent picks up assets with stage='palmier_queued'. Reuses the (ready-state-unused)
    stage field so no migration is needed."""
    a = db.get(VideoAsset, asset_id)
    if a is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    if a.status != "ready":
        raise HTTPException(status_code=422, detail="only ready assets can be queued for finishing")
    a.stage = "palmier_queued"
    db.commit()
    return a


@router.get("/video-assets/{asset_id}/publish-plan", response_model=schemas.PublishPlanOut)
def get_publish_plan(asset_id: int, db: Session = Depends(get_db)) -> PublishPlan:
    """Step-6 companion content for this asset (caption/hashtags/external-link slot/posting time)."""
    plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == asset_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="no publish plan for this asset yet")
    return plan


@router.put("/video-assets/{asset_id}/publish-plan", response_model=schemas.PublishPlanOut)
def upsert_publish_plan(asset_id: int, payload: schemas.PublishPlanIn, db: Session = Depends(get_db)) -> PublishPlan:
    """Create or update the step-6 companion content for a video asset (one plan per asset)."""
    asset = db.get(VideoAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    acc = db.get(Account, asset.account_id)
    plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == asset_id))
    if plan is None:
        plan = PublishPlan(account_id=asset.account_id, video_asset_id=asset_id)
        db.add(plan)
    plan.platform = acc.platform if acc else plan.platform
    plan.caption = payload.caption
    plan.hashtags = list(payload.hashtags or [])
    plan.external_link_slot = payload.external_link_slot
    plan.external_link_text = payload.external_link_text
    plan.posting_time = payload.posting_time
    plan.status = payload.status or "draft"
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/schedule")
def get_schedule(db: Session = Depends(get_db)) -> list[dict]:
    """Every scheduled/generated video with its publish plan, for the date-grouped frontend
    calendar (排期). Ordered by posting_time. Each item carries the date so the UI can bucket
    by day (每日 16 条 = 4 账号 × 4)."""
    rows = db.execute(
        select(PublishPlan, VideoAsset, Account)
        .join(VideoAsset, VideoAsset.id == PublishPlan.video_asset_id)
        .join(Account, Account.id == PublishPlan.account_id)
    ).all()
    items: list[dict] = []
    for plan, asset, acc in rows:
        pt = plan.posting_time or ""
        items.append({
            "date": (pt.split(" ")[0] if pt else ""),
            "posting_time": pt,
            "account_id": acc.id,
            "handle": acc.handle,
            "platform": acc.platform,
            "vertical": acc.vertical,
            "asset_id": asset.id,
            "media_url": asset.media_url,
            "duration": asset.duration,
            "asset_status": asset.status,
            "review_status": asset.review_status,
            "caption": plan.caption,
            "hashtags": plan.hashtags or [],
            "external_link_slot": plan.external_link_slot,
            "plan_status": plan.status,
            "is_seed": bool(asset.dedup_key and asset.dedup_key.startswith("batch-")),
        })
    items.sort(key=lambda x: (x["posting_time"] or "~", x["handle"]))
    return items


@router.post("/video-assets/{asset_id}/regenerate", response_model=schemas.VideoAssetOut, status_code=201)
def regenerate_video(asset_id: int, db: Session = Depends(get_db)) -> VideoAsset:
    """Regenerate a FRESH alternative for this asset's account (new topic->script->hyperframes
    video). Produces a new hf_gen_* asset (never overwrites the old one / the seed 16) and inherits
    the old asset's scheduled posting slot if any. 429 if the daily quota is hit."""
    old = db.get(VideoAsset, asset_id)
    if old is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    acc = db.get(Account, old.account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    from app.analysis.factory import resolve_llm_client
    from app.orchestrator.engine import advance_account
    from app.video.factory import make_account_provider_resolver

    def _latest(aid: int) -> int:
        v = db.scalar(select(VideoAsset).where(VideoAsset.account_id == aid).order_by(VideoAsset.id.desc()))
        return v.id if v else 0

    before = _latest(acc.id)
    try:
        advance_account(db, acc, llm=resolve_llm_client(), video=make_account_provider_resolver(), sync=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"regenerate failed: {exc}") from exc
    after = _latest(acc.id)
    if after <= before:
        raise HTTPException(status_code=409, detail="no new video produced (daily quota reached, or the brain returned no fresh topic)")
    new = db.get(VideoAsset, after)
    new.review_status = "approved"
    # inherit the old asset's posting slot so the calendar keeps its place
    old_plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == asset_id))
    if old_plan is not None:
        plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == new.id))
        if plan is None:
            plan = PublishPlan(account_id=acc.id, video_asset_id=new.id)
            db.add(plan)
        plan.platform = old_plan.platform
        plan.posting_time = old_plan.posting_time
        plan.external_link_slot = old_plan.external_link_slot
        plan.status = "ready"
    db.commit()
    return new


@router.put("/video-assets/{asset_id}/reschedule")
def reschedule_asset(asset_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    """Change a video's scheduled posting time from the calendar UI. Body: {posting_time:"YYYY-MM-DD HH:MM"}."""
    pt = (payload or {}).get("posting_time")
    plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == asset_id))
    if plan is None:
        asset = db.get(VideoAsset, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="video asset not found")
        plan = PublishPlan(account_id=asset.account_id, video_asset_id=asset_id)
        db.add(plan)
    plan.posting_time = pt
    db.commit()
    return {"asset_id": asset_id, "posting_time": plan.posting_time}


@router.post("/schedule/generate-daily", status_code=202)
def generate_daily(rounds: int = Query(default=4, ge=1, le=8),
                   from_trends: bool = Query(default=True)) -> dict:
    """Fire the daily generator (4 accounts x `rounds`) as a detached background job — the UI's
    '生成今日 N 条' button. from_trends=true (default) uses the B-layer's VERIFIED hot topics
    (data-rich, real numbers); false uses in-house topic generation. Returns immediately; new
    videos appear in GET /schedule as they render."""
    import os
    import subprocess
    import sys
    backend_dir = os.getcwd()
    logdir = os.path.join(backend_dir, "..", "logs")
    os.makedirs(logdir, exist_ok=True)
    logf = open(os.path.join(logdir, "generate_daily_api.log"), "a")
    cmd = [sys.executable, "scripts/run_daily_cycle.py", "--rounds", str(rounds)]
    if from_trends:
        cmd.append("--from-trends")
    subprocess.Popen(cmd, cwd=backend_dir, stdout=logf, stderr=logf, start_new_session=True)
    return {"started": True, "rounds": rounds, "from_trends": from_trends}


@router.post("/schedule/run-full-daily", status_code=202)
def run_full_daily(rounds: int = Query(default=4, ge=1, le=8)) -> dict:
    """FULLY autonomous daily (no Claude): web-research verified hot topics -> ingest -> clear
    yesterday's daily -> generate --from-trends -> Obsidian. Detached background job. This is what
    lets matrix-loop reproduce the whole data-rich daily set on its own."""
    import os
    import subprocess
    import sys
    backend_dir = os.getcwd()
    logdir = os.path.join(backend_dir, "..", "logs")
    os.makedirs(logdir, exist_ok=True)
    logf = open(os.path.join(logdir, "run_full_daily.log"), "a")
    subprocess.Popen([sys.executable, "scripts/run_full_daily.py", "--rounds", str(rounds)],
                     cwd=backend_dir, stdout=logf, stderr=logf, start_new_session=True)
    return {"started": True, "rounds": rounds, "steps": ["research", "generate", "obsidian"]}


def _caption_from_plan(db: Session, asset_id: int) -> str | None:
    """Compose a single dispatch caption from the stored publish plan (caption + hashtags)."""
    plan = db.scalar(select(PublishPlan).where(PublishPlan.video_asset_id == asset_id))
    if plan is None:
        return None
    parts = [plan.caption or ""]
    if plan.hashtags:
        parts.append(" ".join(plan.hashtags))
    composed = "\n\n".join(p for p in parts if p).strip()
    return composed or None


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
    # Step-6: prefer the stored publish plan's companion content when no explicit caption is given.
    caption = payload.caption if payload.caption is not None else _caption_from_plan(db, asset.id)
    try:
        return create_dispatch(db, acc, asset, client=client, caption=caption, publish_at=payload.publish_at)
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


@router.post("/trends/ingest", status_code=201)
def ingest_trends(payload: schemas.TrendIngest, db: Session = Depends(get_db)) -> dict:
    incoming = [(t.source.strip().lower(), t.title) for t in payload.trends]
    existing = set(db.execute(
        select(Trend.source, Trend.title).where(
            tuple_(Trend.source, Trend.title).in_(incoming))
    ).all()) if incoming else set()
    ingested = skipped = 0
    seen: set = set()
    for t in payload.trends:
        key = (t.source.strip().lower(), t.title)
        if key in existing or key in seen:
            skipped += 1
            continue
        seen.add(key)
        db.add(Trend(source=key[0], title=t.title, url=t.url, niche=t.niche,
                     engagement=t.engagement, distilled_topic=t.distilled_topic, score=t.score))
        ingested += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="concurrent duplicate trend")
    return {"ingested": ingested, "skipped": skipped}


@router.get("/trends")
def list_trends(niche: str | None = None, limit: int = Query(default=50, le=500), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Trend).order_by(Trend.captured_at.desc(), Trend.id.desc())
    if niche:
        stmt = stmt.where(Trend.niche == niche)
    stmt = stmt.limit(limit)
    return [{"id": t.id, "source": t.source, "title": t.title, "url": t.url, "niche": t.niche,
             "engagement": t.engagement, "distilled_topic": t.distilled_topic, "score": t.score,
             "captured_at": t.captured_at.isoformat() if t.captured_at else None}
            for t in db.scalars(stmt).all()]


# NOTE: /flywheel is a static path (no {param}), so the ordering below is stylistic, not load-bearing.
@router.get("/flywheel/status")
def flywheel_status(db: Session = Depends(get_db)) -> dict:
    return {"paused": is_paused(db), "scheduler_running": scheduler_running()}


@router.post("/flywheel/pause")
def flywheel_pause(db: Session = Depends(get_db)) -> dict:
    set_paused(db, True)
    return {"paused": True}


@router.post("/flywheel/resume")
def flywheel_resume(db: Session = Depends(get_db)) -> dict:
    set_paused(db, False)
    return {"paused": False}


@router.post("/flywheel/scheduler/start")
def scheduler_start() -> dict:
    start_scheduler(SessionLocal)
    return {"scheduler_running": scheduler_running()}


@router.post("/flywheel/scheduler/stop")
def scheduler_stop() -> dict:
    stop_scheduler()
    return {"scheduler_running": scheduler_running()}


@router.get("/flywheel/accounts")
def flywheel_accounts_route(db: Session = Depends(get_db)) -> list[dict]:
    return flywheel_accounts(db)


@router.get("/flywheel/events")
def flywheel_events_route(since_id: int | None = None, account_id: int | None = None,
                          limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return flywheel_events_since(db, since_id=since_id, account_id=account_id, limit=min(limit, 200))


@router.get("/flywheel")
def flywheel(db: Session = Depends(get_db)) -> dict:
    return {**flywheel_state(db), "scheduler_running": scheduler_running()}


# ---------------------------------------------------------------- content calibration
# 盲预测校准闭环 (borrowed from xiaobei content-calibrator): blind score+predict → gate →
# T+Nd review → rubric evolution.

@router.post("/video-assets/{asset_id}/calibrate", response_model=schemas.CalibrationOut)
def calibrate_asset(asset_id: int, db: Session = Depends(get_db)) -> Calibration:
    from app.calibration import calibrator
    asset = db.get(VideoAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    return calibrator.score_and_predict(db, asset, client=resolve_llm_client())


@router.get("/video-assets/{asset_id}/calibration", response_model=schemas.CalibrationOut)
def get_calibration(asset_id: int, db: Session = Depends(get_db)) -> Calibration:
    cal = db.scalar(select(Calibration).where(Calibration.video_asset_id == asset_id))
    if cal is None:
        raise HTTPException(status_code=404, detail="not calibrated yet")
    return cal


@router.get("/calibration/rubric")
def get_rubric_route(db: Session = Depends(get_db)) -> dict:
    from app.calibration import rubric
    return rubric.get_rubric(db)


@router.get("/calibration/summary")
def calibration_summary_route(db: Session = Depends(get_db)) -> dict:
    from app.calibration import calibrator
    return calibrator.calibration_summary(db)


@router.get("/calibration/pending-reviews", response_model=list[schemas.CalibrationOut])
def calibration_pending(db: Session = Depends(get_db)) -> list[Calibration]:
    from app.calibration import calibrator
    return calibrator.pending_reviews(db, min_age_days=settings.calibration_review_days)


@router.post("/calibration/{cal_id}/review", response_model=schemas.CalibrationOut)
def calibration_review(cal_id: int, payload: schemas.CalibrationReviewIn,
                       db: Session = Depends(get_db)) -> Calibration:
    from app.calibration import calibrator
    cal = db.get(Calibration, cal_id)
    if cal is None:
        raise HTTPException(status_code=404, detail="calibration not found")
    try:
        return calibrator.review(db, cal, actual=payload.actual)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/calibration/evolve-rubric")
def calibration_evolve(db: Session = Depends(get_db)) -> dict:
    from app.calibration import calibrator
    try:
        return calibrator.evolve_rubric(db, client=resolve_llm_client())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ---------------------------------------------------------------- smart search (intel intake)

@router.post("/smart-search")
def smart_search_route(payload: schemas.SmartSearchIn, db: Session = Depends(get_db)) -> dict:
    from app.analysis import smart_search
    return smart_search.smart_search(
        db, payload.query, sources=payload.sources, niche=payload.niche,
        limit=payload.limit, client=resolve_llm_client(), distill=payload.distill)


@router.get("/smart-search/sources")
def smart_search_sources() -> dict:
    from app.analysis import smart_search
    return {"sources": smart_search.available_sources()}


# ---------------------------------------------------------------- key-free publish + track

@router.post("/video-assets/{asset_id}/publish-openclaw", response_model=schemas.PublishDispatchOut)
def publish_openclaw_route(asset_id: int, payload: schemas.OpenClawPublishIn,
                           db: Session = Depends(get_db)) -> PublishDispatch:
    from app.publish.openclaw import publish_via_openclaw
    from app.publish.dispatch import PublishNotReady
    asset = db.get(VideoAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="video asset not found")
    account = db.get(Account, asset.account_id)
    try:
        return publish_via_openclaw(
            db, account, asset, platform=payload.platform, caption=payload.caption,
            enforce_gate=settings.calibration_enforce_gate)
    except PublishNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/publish/track")
def publish_track_route(account_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    from app.publish.track import track_summary
    return track_summary(db, account_id=account_id)
