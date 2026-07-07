from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, ContentItem, Draft, Evaluation, LoopRun, Recommendation, Snapshot


def _latest_eval(session, account_id):
    return session.scalars(
        select(Evaluation).where(Evaluation.account_id == account_id)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    ).first()


def _latest_loop(session, account_id):
    return session.scalars(
        select(LoopRun).where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
    ).first()


def _ordered_snaps(session, account_id):
    return session.scalars(
        select(Snapshot).where(Snapshot.account_id == account_id).order_by(Snapshot.ts)
    ).all()


def build_overview(session: Session) -> dict:
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())

    evals = {a.id: _latest_eval(session, a.id) for a in accounts}
    loops = {a.id: _latest_loop(session, a.id) for a in accounts}

    scored = [evals[a.id].composite_score for a in accounts if evals[a.id]]
    avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0
    needs_attention = sum(1 for a in accounts if loops[a.id] and loops[a.id].status == "no_progress")
    pending_recs = session.scalars(select(Recommendation).where(Recommendation.status == "pending")).all()
    pending_drafts = session.scalars(select(Draft).where(Draft.review_status == "pending")).all()

    # platform health: avg of latest-eval breakdown per objective, grouped by platform
    dims = ["growth", "engagement", "commercial", "positioning"]
    by_platform: dict[str, list] = {}
    for a in accounts:
        ev = evals[a.id]
        if ev:
            by_platform.setdefault(a.platform, []).append(ev.breakdown or {})
    platform_health = []
    for platform, rows in by_platform.items():
        entry = {"platform": platform}
        for d in dims:
            vals = [r.get(d, 0) for r in rows]
            entry[d] = round(sum(vals) / len(vals), 1) if vals else 0.0
        platform_health.append(entry)

    # matrix-wide trend: aggregate followers + avg engagement by snapshot date
    trend_acc: dict[str, dict] = {}
    for a in accounts:
        for s in _ordered_snaps(session, a.id):
            day = s.ts.date().isoformat()
            t = trend_acc.setdefault(day, {"date": day, "followers": 0, "_er": []})
            t["followers"] += s.followers or 0
            if s.engagement_rate is not None:
                t["_er"].append(s.engagement_rate)
    trend = []
    for day in sorted(trend_acc):
        t = trend_acc[day]
        er = t.pop("_er")
        t["engagement"] = round(sum(er) / len(er), 4) if er else 0.0
        trend.append(t)

    # alerts
    alerts = []
    for a in accounts:
        lp = loops[a.id]
        if lp and lp.status == "no_progress":
            alerts.append({"account_id": a.id, "handle": a.handle, "platform": a.platform,
                           "kind": "no_progress", "detail": "连续无进展，需介入"})
    # pending drafts per account — join via loop_run relationship
    pend_draft_by_acct: dict[int, int] = {}
    for d in pending_drafts:
        acct = d.loop_run.account_id
        pend_draft_by_acct[acct] = pend_draft_by_acct.get(acct, 0) + 1
    handle_by_id = {a.id: a for a in accounts}
    for acct_id, n in pend_draft_by_acct.items():
        a = handle_by_id.get(acct_id)
        if a:
            alerts.append({"account_id": acct_id, "handle": a.handle, "platform": a.platform,
                           "kind": "pending_drafts", "detail": f"{n} 条草稿待审"})

    # top movers: latest followers - previous followers
    movers = []
    for a in accounts:
        snaps = _ordered_snaps(session, a.id)
        if len(snaps) >= 2 and snaps[-1].followers is not None and snaps[-2].followers is not None:
            movers.append({"account_id": a.id, "handle": a.handle, "platform": a.platform,
                           "delta_followers": snaps[-1].followers - snaps[-2].followers})
    movers.sort(key=lambda m: m["delta_followers"], reverse=True)

    # positioning distribution from latest eval positioning subscore
    dist = {"clear": 0, "ok": 0, "scattered": 0}
    for a in accounts:
        ev = evals[a.id]
        if ev:
            p = (ev.breakdown or {}).get("positioning", 0)
            dist["clear" if p >= 70 else "scattered" if p < 40 else "ok"] += 1

    return {
        "kpis": {
            "total_accounts": len(accounts),
            "avg_score": avg_score,
            "needs_attention": needs_attention,
            "platforms": len({a.platform for a in accounts}),
            "pending_review": len(pending_recs) + len(pending_drafts),
        },
        "platform_health": platform_health,
        "trend": trend,
        "alerts": alerts,
        "top_movers": movers[:10],
        "positioning_distribution": dist,
    }
