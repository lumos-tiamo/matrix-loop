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


def flywheel_state(session: Session, *, event_limit: int = 20) -> dict:
    """Aggregate live per-step counts + per-account autopilot state + recent audit events for the UI."""
    from app.models import (Account, ContentItem, Draft, FlywheelEvent, PublishDispatch, Trend, VideoAsset)
    from sqlalchemy import func, select as _select

    def _count(stmt) -> int:
        return int(session.scalar(stmt) or 0)

    trends_n = _count(_select(func.count(Trend.id)))
    topics = _count(_select(func.count(Draft.id)).where(Draft.kind == "topic"))
    scripts = _count(_select(func.count(Draft.id)).where(Draft.kind == "script"))
    videos = _count(_select(func.count(VideoAsset.id)))
    pending_vid = _count(_select(func.count(VideoAsset.id)).where(VideoAsset.review_status == "pending"))
    dispatches = _count(_select(func.count(PublishDispatch.id)))
    published = _count(_select(func.count(PublishDispatch.id)).where(PublishDispatch.status == "published"))
    tracked = _count(_select(func.count(ContentItem.id)).where(ContentItem.platform_post_id.is_not(None)))
    accounts_total = _count(_select(func.count(Account.id)))
    autopilot_n = _count(_select(func.count(Account.id)).where(Account.autopilot.is_(True)))

    steps = [
        {"key": "crawl",    "label": "爬爆款",   "count": trends_n,    "status": "ok" if trends_n else "pending"},
        {"key": "brief",    "label": "定调",     "count": accounts_total, "status": "ok"},
        {"key": "script",   "label": "脚本",     "count": scripts,     "status": "ok" if scripts else "pending"},
        {"key": "video",    "label": "视频",     "count": videos,      "status": "ok" if videos else "pending"},
        {"key": "publish",  "label": "发布",     "count": dispatches,  "status": "ok" if dispatches else "pending"},
        {"key": "track",    "label": "追踪流量", "count": tracked,     "status": "ok" if tracked else "pending"},
        {"key": "retro",    "label": "复盘",     "count": published,   "status": "ok" if published else "pending"},
        {"key": "evaluate", "label": "账号评估", "count": accounts_total, "status": "ok"},
        {"key": "improve",  "label": "改进建议", "count": topics,      "status": "ok" if topics else "pending"},
    ]
    accts = [
        {"id": a.id, "handle": a.handle, "platform": a.platform, "autopilot": a.autopilot}
        for a in session.scalars(_select(Account).order_by(Account.id)).all()
    ]
    evs = session.scalars(
        _select(FlywheelEvent).order_by(FlywheelEvent.id.desc()).limit(event_limit)
    ).all()
    events = [{"account_id": e.account_id, "step": e.step, "status": e.status,
               "detail": e.detail, "ts": e.ts.isoformat() if e.ts else None} for e in evs]
    return {"paused": is_paused(session), "autopilot_accounts": autopilot_n,
            "steps": steps, "accounts": accts, "events": events, "pending_review": pending_vid}
