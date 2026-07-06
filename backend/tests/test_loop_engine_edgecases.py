"""Regression tests for edge cases in run_loop (plan-4 review fixes)."""
from datetime import datetime, timezone

import pytest

from app.models import Account, ContentItem, LoopRun, Recommendation, Snapshot
from app.loop.engine import run_loop


def _make_account(session):
    acc = Account(
        platform="x",
        handle="@edge",
        objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0},
    )
    session.add(acc)
    session.commit()
    return acc


def _add_snap(session, acc, day, followers):
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, day, tzinfo=timezone.utc), followers=followers))
    session.commit()


def _add_content(session, acc):
    session.add(ContentItem(account_id=acc.id, views=100, topic="tech"))
    session.commit()


# ---------------------------------------------------------------------------
# Test 1: prev run without evaluation is treated as baseline
# ---------------------------------------------------------------------------
def test_prev_run_without_evaluation_is_baseline(session):
    acc = _make_account(session)

    # Manually persist a LoopRun with status="error" and NO evaluation attached
    orphan_run = LoopRun(account_id=acc.id, status="error")
    session.add(orphan_run)
    session.commit()
    assert orphan_run.evaluation is None

    # Seed one pair of snapshots so scoring works (+5% growth -> composite 50)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 105000)

    run = run_loop(session, acc)
    assert run.verify_result["baseline"] is True


# ---------------------------------------------------------------------------
# Test 2: multiple adopted recommendations all get marked "worked"
# ---------------------------------------------------------------------------
def test_multiple_adopted_recommendations_all_marked_worked(session):
    acc = _make_account(session)

    # Seed: 100k -> 105k (+5% -> composite 50)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 105000)

    run1 = run_loop(session, acc)
    assert run1.verify_result["baseline"] is True

    # Mark ALL existing recommendations as "adopted" and add a guaranteed second one
    for rec in run1.recommendations:
        rec.status = "adopted"

    extra_rec = Recommendation(
        loop_run_id=run1.id,
        kind="content_direction",
        content="额外建议",
        status="adopted",
    )
    session.add(extra_rec)
    session.commit()

    # Refresh the relationship so the extra rec is visible in the collection
    session.expire(run1)
    adopted_before = [r for r in run1.recommendations if r.status == "adopted"]
    assert len(adopted_before) >= 2

    # Add snapshot to reach +10% overall (100k -> 110k -> composite 100)
    _add_snap(session, acc, 6, 110000)

    run2 = run_loop(session, acc)

    # run2 must have improved (composite went 50 -> 100, delta = 50 > 0.5)
    assert run2.verify_result["improved"] is True

    # Reload run1's recommendations from the session to get updated statuses
    session.expire(run1)
    worked_recs = [r for r in run1.recommendations if r.status == "worked"]
    assert len(worked_recs) >= 2
