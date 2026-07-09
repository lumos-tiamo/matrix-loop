from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trend


def trend_prompt_block(session: Session, niches: list[str] | None = None, *, limit: int = 8) -> str:
    """Format recent viral trends into a prompt block so generation leans into what's hot now."""
    stmt = select(Trend).order_by(Trend.captured_at.desc(), Trend.id.desc())
    if niches:
        stmt = stmt.where(Trend.niche.in_(niches))
    rows = list(session.scalars(stmt.limit(limit)).all())
    if not rows:
        return ""
    lines = []
    for t in rows:
        angle = t.distilled_topic or t.title
        tag = f" [{t.niche}]" if t.niche else ""
        lines.append(f'- "{angle}" ({t.source}{tag})')
    return "Currently trending viral angles — lean into what's hot right now:\n" + "\n".join(lines)
