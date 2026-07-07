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
from app.scheduler.runs import BATCH_RUNS, new_run_id, start_batch

logger = logging.getLogger(__name__)
from app.ingest.manual_import import import_snapshots_csv
from app.loop.engine import run_loop
from app.api.overview import build_overview
from app.models import Account, AccountSegment, AudienceSegment, ContentItem, Draft, Endpoint, Evaluation, LoopRun, Recommendation, Snapshot
from app.flow.build import build_flow
from app.flow.classify import classify_audience
from app.analysis.claude_client import ClaudeClient

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
    from collections import defaultdict
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
        return run_loop(db, acc)
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
        BATCH_RUNS[run_id] = {"status": "running", "report": None, "error": None}
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
