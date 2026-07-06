from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.loop.engine import run_loop, LoopConfig


def test_flat_runs_trigger_no_progress(session):
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    # 固定两点 100k->110k，复合分恒为 100，不随重复 run 变化
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()

    cfg = LoopConfig(no_progress_limit=3, min_improvement=0.5)
    statuses = [run_loop(session, acc, cfg=cfg).status for _ in range(4)]
    # 前 3 轮历史不足，ok；第 4 轮已有 3 条持平历史 -> no_progress
    assert statuses[:3] == ["ok", "ok", "ok"]
    assert statuses[3] == "no_progress"
