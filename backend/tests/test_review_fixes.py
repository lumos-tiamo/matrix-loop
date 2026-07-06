"""Tests added for code-review fixes (JSON defaults, unique constraint,
atomic import, loop_runs back-reference)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Account, ContentItem, Evaluation, LoopRun, Snapshot


# ---------------------------------------------------------------------------
# Fix #1 – JSON columns have defaults on freshly-constructed (unsaved) instances
# ---------------------------------------------------------------------------

def test_account_objective_weights_default_before_flush():
    acc = Account(platform="x", handle="h")
    assert acc.objective_weights == {
        "growth": 0.25,
        "engagement": 0.25,
        "commercial": 0.25,
        "positioning": 0.25,
    }


def test_snapshot_extra_default_before_flush():
    snap = Snapshot(account_id=1, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert snap.extra == {}


def test_content_item_extra_default_before_flush():
    ci = ContentItem(account_id=1)
    assert ci.extra == {}


def test_loop_run_verify_result_default_before_flush():
    run = LoopRun(account_id=1)
    assert run.verify_result == {}


def test_evaluation_breakdown_default_before_flush():
    ev = Evaluation(account_id=1, composite_score=75.0)
    assert ev.breakdown == {}


def test_json_defaults_are_independent_instances():
    """Each instance must get its own dict, not a shared reference."""
    a1 = Account(platform="x", handle="h1")
    a2 = Account(platform="x", handle="h2")
    a1.objective_weights["growth"] = 0.99
    assert a2.objective_weights["growth"] == 0.25

    s1 = Snapshot(account_id=1, ts=datetime(2026, 1, 1, tzinfo=timezone.utc))
    s2 = Snapshot(account_id=1, ts=datetime(2026, 1, 2, tzinfo=timezone.utc))
    s1.extra["k"] = "v"
    assert s2.extra == {}


# ---------------------------------------------------------------------------
# Fix #2 – (platform, handle) unique constraint
# ---------------------------------------------------------------------------

def test_duplicate_account_raises_integrity_error(session):
    session.add(Account(platform="x", handle="@dup"))
    session.commit()
    session.add(Account(platform="x", handle="@dup"))
    with pytest.raises(IntegrityError):
        session.flush()


# ---------------------------------------------------------------------------
# Fix #3 – atomic CSV import rolls back on error
# ---------------------------------------------------------------------------

BAD_CSV = """platform,handle,ts,followers
goodplatform,@ok,2026-07-06T00:00:00+00:00,1000
goodplatform,@ok,NOT_A_TIMESTAMP,2000
"""


def test_import_rollback_on_bad_row(session):
    from app.ingest.manual_import import import_snapshots_csv

    with pytest.raises(Exception):
        import_snapshots_csv(session, io.StringIO(BAD_CSV))

    assert session.query(Account).count() == 0
    assert session.query(Snapshot).count() == 0


# ---------------------------------------------------------------------------
# Fix #7 – Account.loop_runs back-reference
# ---------------------------------------------------------------------------

def test_account_loop_runs_back_reference(session):
    acc = Account(platform="x", handle="@lr_test")
    session.add(acc)
    session.commit()

    run = LoopRun(account_id=acc.id, status="ok", tokens_cost=0)
    session.add(run)
    session.commit()

    session.refresh(acc)
    assert len(acc.loop_runs) == 1
    assert acc.loop_runs[0].id == run.id
    assert run.account.handle == "@lr_test"
