from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import get_db
from app.connectors.base import ManualOnlyError
from app.connectors.sync import sync_account

logger = logging.getLogger(__name__)
from app.ingest.manual_import import import_snapshots_csv
from app.loop.engine import run_loop
from app.models import Account, Draft, Evaluation, LoopRun, Recommendation, Snapshot

router = APIRouter()


def _latest(db: Session, model, account_id: int, *order):
    stmt = select(model).where(model.account_id == account_id).order_by(*order)
    return db.scalars(stmt).first()


def _list_item(db: Session, acc: Account) -> schemas.AccountListItem:
    snap = _latest(db, Snapshot, acc.id, Snapshot.ts.desc(), Snapshot.id.desc())
    ev = _latest(db, Evaluation, acc.id, Evaluation.created_at.desc(), Evaluation.id.desc())
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
    # TODO(perf): replace per-account _list_item queries with one aggregating query when accounts > ~200
    accounts = db.scalars(select(Account).order_by(Account.id)).all()
    return [_list_item(db, a) for a in accounts]


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
