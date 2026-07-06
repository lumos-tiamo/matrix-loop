from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.loop.engine import run_loop


def _acc(session):
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    return acc


def _add_snap(session, acc, day, followers):
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, day, tzinfo=timezone.utc), followers=followers))
    session.commit()


def test_second_run_improved_marks_prev_adopted_rec_worked(session):
    acc = _acc(session)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 105000)   # +5% -> growth 50 -> composite 50
    run1 = run_loop(session, acc)
    assert run1.verify_result["baseline"] is True
    # 用户采纳了 run1 的一条建议
    run1.recommendations[0].status = "adopted"
    session.commit()

    _add_snap(session, acc, 6, 110000)   # 100k->110k = +10% -> growth 100 -> composite 100
    run2 = run_loop(session, acc)
    assert run2.verify_result["baseline"] is False
    assert run2.verify_result["improved"] is True
    assert run2.verify_result["delta"] == 50.0
    assert run1.recommendations[0].status == "worked"


def test_second_run_not_improved_marks_prev_adopted_rec_failed(session):
    acc = _acc(session)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 110000)   # +10% -> composite 100
    run1 = run_loop(session, acc)
    run1.recommendations[0].status = "adopted"
    session.commit()

    # 再加一个点让首末仍是 100k->110k（复合分不变）
    _add_snap(session, acc, 6, 110000)
    run2 = run_loop(session, acc)
    assert run2.verify_result["improved"] is False
    assert run2.verify_result["delta"] == 0.0
    assert run1.recommendations[0].status == "failed"
