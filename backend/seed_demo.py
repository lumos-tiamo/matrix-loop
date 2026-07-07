"""Seed a demo dataset so the Dashboard has realistic content to render.

Idempotent: does nothing if accounts already exist. Run from backend/ with the venv:
    python seed_demo.py
Creates ./data/matrixloop.db (same DB uvicorn serves).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401  register models
from app.models import (
    Account, AccountSegment, AudienceSegment, ContentItem, Endpoint, Snapshot,
)
from app.loop.engine import run_loop, LoopConfig


def _d(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=timezone.utc)


# (platform, handle, vertical, weights, follower_series, topics)
DEMO = [
    ("xiaohongshu", "@beauty_lab", "beauty",
     {"growth": 0.4, "engagement": 0.3, "commercial": 0.2, "positioning": 0.1},
     [88000, 92000, 99000], ["beauty", "beauty", "skincare", "beauty", "beauty"]),
    ("douyin", "@tech_daily", "tech",
     {"growth": 0.5, "engagement": 0.3, "commercial": 0.1, "positioning": 0.1},
     [120000, 121000, 122500], ["ai", "gadgets", "coding", "startup", "ai"]),
    ("tiktok", "@fit_coach", "fitness",
     {"growth": 0.6, "engagement": 0.2, "commercial": 0.2, "positioning": 0.0},
     [45000, 47000], ["fitness", "fitness", "nutrition"]),
    ("twitter", "@money_talk", "finance",
     {"growth": 0.3, "engagement": 0.4, "commercial": 0.3, "positioning": 0.0},
     [210000, 214000, 219000], ["markets", "crypto", "macro", "markets"]),
    ("bilibili", "@travel_vlog", "travel",
     {"growth": 0.4, "engagement": 0.3, "commercial": 0.1, "positioning": 0.2},
     [67000, 68000], ["japan", "food", "budget", "gear", "japan"]),
    # flat account -> will hit no_progress after repeated runs (populates the queue)
    ("xiaohongshu", "@food_wander", "food",
     {"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0},
     [30000, 30000], ["food"]),
]

ENGAGEMENT = {"@beauty_lab": 0.061, "@tech_daily": 0.028, "@fit_coach": 0.045,
              "@money_talk": 0.038, "@travel_vlog": 0.052, "@food_wander": 0.011}

# ---- 导流/转化 (flow / sankey) demo ----
# 变现出口 (endpoint name -> bio 外链子串 for auto-match)
DEMO_ENDPOINTS: list[tuple[str, str | None]] = [
    ("Nina", "linktr.ee/nina"),
    ("xaue", "xaue.com"),
    ("私域社群", "t.me/matrixloop"),
]
# 人群标签 (audience segments)
DEMO_SEGMENTS = ["crypto", "海外投资者", "宝妈", "打工人群"]
# 账号 -> (出口名 or None=未定向, [(人群标签, 占比), ...])
DEMO_ASSIGN: dict[str, tuple[str | None, list[tuple[str, float]]]] = {
    "@money_talk": ("Nina", [("crypto", 0.6), ("海外投资者", 0.4)]),
    "@tech_daily": ("xaue", [("crypto", 0.5), ("打工人群", 0.5)]),
    "@beauty_lab": ("私域社群", [("宝妈", 0.7), ("打工人群", 0.3)]),
    "@travel_vlog": (None, [("海外投资者", 0.4), ("打工人群", 0.6)]),
    "@fit_coach": ("私域社群", [("打工人群", 1.0)]),
}


def seed_flow(db) -> None:
    """Seed endpoints / audience segments / account compositions for the /flow sankey.

    Guarded: only runs the first time (no Endpoint rows yet), so re-running the seeder
    or running it against an already-seeded (pre-flow) DB stays idempotent and safe.
    """
    if db.query(Endpoint).count() > 0:
        print("flow already seeded; skipping")
        return

    endpoints = {name: Endpoint(name=name, url_pattern=pat) for name, pat in DEMO_ENDPOINTS}
    db.add_all(endpoints.values())
    segments = {label: AudienceSegment(label=label) for label in DEMO_SEGMENTS}
    db.add_all(segments.values())
    db.commit()

    accounts = {a.handle: a for a in db.query(Account).all()}
    assigned = 0
    for handle, (ep_name, comps) in DEMO_ASSIGN.items():
        acc = accounts.get(handle)
        if acc is None:
            continue
        acc.endpoint_id = endpoints[ep_name].id if ep_name else None
        for label, weight in comps:
            db.add(AccountSegment(account_id=acc.id, segment_id=segments[label].id, weight=weight))
        assigned += 1
    db.commit()
    print(f"seeded flow: {len(endpoints)} endpoints, {len(segments)} segments, {assigned} accounts routed")


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(Account).count() > 0:
        print("already seeded; skipping accounts")
        seed_flow(db)  # backfill flow demo onto a pre-flow seeded DB (guarded internally)
        return

    for platform, handle, vertical, weights, followers, topics in DEMO:
        acc = Account(platform=platform, handle=handle, vertical=vertical,
                      objective_weights=weights, positioning=f"{vertical} 内容")
        db.add(acc)
        db.commit()

        for i, f in enumerate(followers):
            db.add(Snapshot(account_id=acc.id, ts=_d(1 + i * 2), followers=f,
                            engagement_rate=ENGAGEMENT[handle],
                            hit_rate=0.12 if handle != "@food_wander" else 0.02,
                            conversions=5 if vertical in ("finance", "beauty") else 1,
                            source_tier={"xiaohongshu": "manual", "douyin": "scrape",
                                         "tiktok": "scrape", "twitter": "api",
                                         "bilibili": "manual"}[platform]))
        views = [800, 1500, 950, 6200, 1100][: len(topics)] or [1000]
        for t, v in zip(topics, (views * 3)[: len(topics)]):
            db.add(ContentItem(account_id=acc.id, topic=t, views=v, likes=v // 10))
        db.commit()

        # @food_wander: run 4x on flat data -> no_progress; others run once
        runs = 4 if handle == "@food_wander" else 1
        for _ in range(runs):
            run_loop(db, acc, cfg=LoopConfig(no_progress_limit=3, min_improvement=0.5))

    print(f"seeded {db.query(Account).count()} accounts")
    seed_flow(db)


if __name__ == "__main__":
    main()
