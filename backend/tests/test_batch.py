from datetime import datetime, timezone

import app.scheduler.batch as batch_mod
from app.models import Account, Snapshot, LoopRun
from app.scheduler.batch import run_batch, BatchConfig


def _acct(session, handle, followers=(100000, 110000)):
    acc = Account(platform="twitter", handle=handle, objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    for i, f in enumerate(followers):
        session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1 + i * 2, tzinfo=timezone.utc), followers=f))
    session.commit()
    return acc


def test_run_batch_loops_all_accounts(session):
    _acct(session, "@a1"); _acct(session, "@a2"); _acct(session, "@a3")
    report = run_batch(session, sync=False)
    assert report.processed == 3
    assert report.looped == 3
    assert report.errors == []
    assert session.query(LoopRun).count() == 3


def test_run_batch_isolates_per_account_error(session, monkeypatch):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2"); a3 = _acct(session, "@a3")
    real = batch_mod.run_loop

    def flaky(sess, account, **kw):
        if account.id == a2.id:
            raise RuntimeError("boom")
        return real(sess, account, **kw)

    monkeypatch.setattr(batch_mod, "run_loop", flaky)
    report = run_batch(session, sync=False)
    assert report.processed == 3
    assert report.looped == 2                       # a1, a3 succeeded
    assert len(report.errors) == 1
    assert report.errors[0]["account_id"] == a2.id
    assert report.errors[0]["stage"] == "loop"


def test_run_batch_max_accounts_caps(session):
    for i in range(5):
        _acct(session, f"@a{i}")
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(max_accounts=2))
    assert report.processed == 2
    assert report.looped == 2


def test_run_batch_collects_no_progress(session):
    acc = Account(platform="twitter", handle="@flat", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()
    # must exceed LoopConfig.no_progress_limit (default 3) so the 4th run flags no_progress
    for _ in range(4):
        report = run_batch(session, sync=False)
    assert acc.id in report.no_progress


def test_run_batch_offset_rotates(session):
    accts = [_acct(session, f"@r{i}") for i in range(5)]
    ids = [a.id for a in accts]
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(offset=2, max_accounts=2))
    assert report.processed == 2
    loop_runs = session.query(LoopRun).all()
    processed_ids = {r.account_id for r in loop_runs}
    # offset=2 skips the first two by id; the next two are ids[2] and ids[3]
    assert processed_ids == {ids[2], ids[3]}


def test_run_batch_circuit_breaker(session, monkeypatch):
    for i in range(6):
        _acct(session, f"@a{i}")

    def always_fail(sess, account, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(batch_mod, "run_loop", always_fail)
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(stop_after_consecutive_errors=3))
    assert report.stopped_early is True
    assert len(report.errors) == 3           # stopped after 3 consecutive
    assert report.processed == 3
