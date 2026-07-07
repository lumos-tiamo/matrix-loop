from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import get_db
from app.ingest.manual_import import import_snapshots_csv
from app.loop.engine import run_loop
from app.models import Account, Evaluation, LoopRun, Snapshot

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
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    acc = Account(**data)
    db.add(acc)
    db.commit()
    return _list_item(db, acc)


@router.get("/accounts", response_model=list[schemas.AccountListItem])
def list_accounts(db: Session = Depends(get_db)) -> list[schemas.AccountListItem]:
    accounts = db.scalars(select(Account).order_by(Account.id)).all()
    return [_list_item(db, a) for a in accounts]


@router.get("/accounts/{account_id}", response_model=schemas.AccountDetail)
def get_account(account_id: int, db: Session = Depends(get_db)) -> Account:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return acc


@router.post("/import/snapshots")
def import_snapshots(payload: dict, db: Session = Depends(get_db)) -> dict:
    csv_text = payload.get("csv", "")
    return import_snapshots_csv(db, io.StringIO(csv_text))


@router.post("/accounts/{account_id}/loop", response_model=schemas.LoopRunOut)
def trigger_loop(account_id: int, db: Session = Depends(get_db)) -> LoopRun:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return run_loop(db, acc)
