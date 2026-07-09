from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AppState

_PAUSE_KEY = "flywheel_paused"


def is_paused(session: Session) -> bool:
    row = session.get(AppState, _PAUSE_KEY)
    return bool(row and row.value == "1")


def set_paused(session: Session, paused: bool) -> None:
    row = session.get(AppState, _PAUSE_KEY)
    if row is None:
        row = AppState(key=_PAUSE_KEY)
        session.add(row)
    row.value = "1" if paused else "0"
    session.commit()
