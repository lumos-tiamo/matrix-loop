from datetime import datetime, timezone

from app.models import Account, Snapshot, LoopRun


def _seed_manual_account(session, handle):
    acc = Account(platform="xiaohongshu", handle=handle, objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
    ])
    session.commit()
    return acc


def test_batch_run_endpoint(client, session):
    for h in ("@b1", "@b2"):
        acc = Account(platform="xiaohongshu", handle=h, objective_weights={
            "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc)
        session.commit()
        session.add_all([
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
        ])
        session.commit()

    # sync=false via query param so manual platforms don't need connectors
    resp = client.post("/batch/run?sync=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 2
    assert body["looped"] == 2
    assert body["errors"] == []
    assert session.query(LoopRun).count() == 2


def test_batch_run_respects_max_accounts(client, session):
    for h in ("@m1", "@m2", "@m3"):
        _seed_manual_account(session, h)

    resp = client.post("/batch/run?sync=false&max_accounts=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 1
