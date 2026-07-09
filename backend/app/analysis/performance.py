from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem


def content_performance(session: Session, account_id: int, *, top: int = 3) -> dict:
    """Rank this account's content by real views. Excludes items with no views."""
    items = session.scalars(
        select(ContentItem)
        .where(ContentItem.account_id == account_id, ContentItem.views.is_not(None))
        .order_by(ContentItem.views.desc())
    ).all()
    if not items:
        return {"winners": [], "losers": [], "median_views": 0.0, "count": 0}
    views = sorted(i.views or 0 for i in items)
    n = len(views)
    median = float(views[n // 2] if n % 2 else (views[n // 2 - 1] + views[n // 2]) / 2)

    def _row(i):
        return {"topic": (i.topic or "")[:80], "views": i.views, "likes": i.likes}

    winners = [_row(i) for i in items[:top]]
    losers = [_row(i) for i in items[-top:]]
    return {"winners": winners, "losers": losers, "median_views": median, "count": n}


def performance_prompt_block(perf: dict) -> str:
    if not perf.get("count"):
        return ""
    def _fmt(rows):
        return "; ".join(f'"{r["topic"]}" ({r["views"]} views)' for r in rows) or "(none)"
    return (
        "Past content performance on this account — lean into what worked:\n"
        f"Top performers: {_fmt(perf['winners'])}\n"
        f"Underperformers: {_fmt(perf['losers'])}\n"
        "Bias the new topic/script toward the winning angles; avoid the ones that flopped."
    )
