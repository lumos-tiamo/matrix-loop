from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Draft, VideoAsset


def assign_voice(account_id: int, pool: list[str]) -> str:
    """Deterministically pick a TTS voice for an account from a pool, spreading load so the
    matrix does not collapse into a few clusterable voice fingerprints."""
    if not pool:
        return "default"
    return pool[account_id % len(pool)]


def _tokens(text: str) -> set[str]:
    return {t for t in (text or "").lower().split() if t}


def script_similarity(a: str, b: str) -> float:
    """Jaccard token overlap in [0, 1]. 1.0 = identical token sets, 0.0 = disjoint."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return round(inter / union, 4) if union else 0.0


def is_near_duplicate_script(session: Session, account_id: int, script: str,
                             threshold: float = 0.85, limit: int = 200) -> bool:
    """True if `script` is >= threshold similar to a recent script used to make a VideoAsset
    on a DIFFERENT account (a matrix-differentiation guard). The account's own scripts are
    excluded (that is dedup's job, not differentiation)."""
    stmt = (
        select(Draft.content)
        .join(VideoAsset, VideoAsset.script_draft_id == Draft.id)
        .where(VideoAsset.account_id != account_id)
        .order_by(VideoAsset.id.desc())
        .limit(limit)
    )
    for (content,) in session.execute(stmt):
        if script_similarity(script, content) >= threshold:
            return True
    return False
