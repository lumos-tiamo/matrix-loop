from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
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


STEP_ORDER = ["sync", "evaluate", "topic", "script", "video", "approve", "publish", "track"]


def _aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on read; normalise to UTC-aware for arithmetic."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _derive_status(cycle_events):
    if not cycle_events:
        return "idle", STEP_ORDER[0], 0, 0, None
    last = cycle_events[-1]
    done = {e.step for e in cycle_events if e.status in ("ok", "skipped")}
    steps_done = sum(1 for s in STEP_ORDER if s in done)
    if last.status == "error":
        return "error", last.step, STEP_ORDER.index(last.step), steps_done, last.detail
    if last.status == "blocked":
        return "blocked", last.step, STEP_ORDER.index(last.step), steps_done, last.detail
    if last.step == STEP_ORDER[-1] and last.status in ("ok", "skipped"):
        return "ok", STEP_ORDER[-1], len(STEP_ORDER) - 1, steps_done, None
    idx = min(STEP_ORDER.index(last.step) + 1, len(STEP_ORDER) - 1)
    return "running", STEP_ORDER[idx], idx, steps_done, None


def flywheel_accounts(session) -> list[dict]:
    from app.models import Account, FlywheelEvent, Evaluation, Snapshot, VideoAsset
    from app.config import settings
    now = datetime.now(timezone.utc)
    interval_min = settings.orchestrator_interval_minutes
    out = []
    accts = session.scalars(
        select(Account).where(Account.autopilot.is_(True)).order_by(Account.id)
    ).all()
    for a in accts:
        last_ev = session.scalars(
            select(FlywheelEvent).where(FlywheelEvent.account_id == a.id)
            .order_by(FlywheelEvent.id.desc()).limit(1)
        ).first()
        cycle_events = []
        if last_ev and last_ev.cycle_id:
            cycle_events = session.scalars(
                select(FlywheelEvent).where(
                    FlywheelEvent.account_id == a.id,
                    FlywheelEvent.cycle_id == last_ev.cycle_id,
                ).order_by(FlywheelEvent.id.asc())
            ).all()
        status, current_step, step_index, steps_done, blocked_reason = _derive_status(cycle_events)
        elapsed = int((now - _aware(last_ev.ts)).total_seconds()) if last_ev else None
        snaps = session.scalars(
            select(Snapshot).where(Snapshot.account_id == a.id).order_by(Snapshot.ts.desc()).limit(2)
        ).all()
        latest, prev = (snaps[0] if snaps else None), (snaps[1] if len(snaps) > 1 else None)
        fol_delta = None
        if latest and prev and prev.followers:
            fol_delta = round((latest.followers - prev.followers) / prev.followers * 100, 1)
        ev = session.scalars(
            select(Evaluation).where(Evaluation.account_id == a.id).order_by(Evaluation.id.desc()).limit(1)
        ).first()
        cost_cycle = 0.0
        if cycle_events:
            cost_cycle = float(session.scalar(
                select(func.coalesce(func.sum(VideoAsset.cost), 0.0))
                .where(VideoAsset.account_id == a.id, VideoAsset.created_at >= cycle_events[0].ts)
            ) or 0.0)
        next_eta = None
        if status in ("ok", "idle") and last_ev:
            next_eta = max(0, int(interval_min * 60 - (now - _aware(last_ev.ts)).total_seconds()))
        out.append({
            "account_id": a.id, "platform": a.platform, "handle": a.handle, "autopilot": a.autopilot,
            "status": status, "current_step": current_step, "step_index": step_index,
            "steps_done": steps_done, "elapsed_sec": elapsed, "blocked_reason": blocked_reason,
            "last_event": ({"step": last_ev.step, "status": last_ev.status,
                            "detail": last_ev.detail, "ts": last_ev.ts.isoformat()} if last_ev else None),
            "kpis": {"followers": latest.followers if latest else None,
                     "followers_delta": fol_delta,
                     "views_7d": latest.views if latest else None,
                     "score": round(ev.composite_score) if ev else None},
            "cost_cycle": round(cost_cycle, 2),
            "next_run_eta_sec": next_eta,
            "synced_at": latest.ts.isoformat() if latest else None,
        })
    return out
