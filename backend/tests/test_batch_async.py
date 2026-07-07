from datetime import datetime, timezone

import app.scheduler.runs as runs_mod
from app.models import Account, Snapshot
from app.scheduler.runs import BATCH_RUNS, start_batch, new_run_id


def _seed(session):
    for h in ("@a", "@b"):
        acc = Account(platform="twitter", handle=h, objective_weights={
            "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc); session.commit()
        session.add_all([
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
        ])
        session.commit()


def test_start_batch_populates_registry(session):
    _seed(session)
    rid = new_run_id()
    BATCH_RUNS.clear()
    start_batch(rid, lambda: session, sync=False)
    entry = BATCH_RUNS[rid]
    assert entry["status"] == "completed"
    assert entry["report"]["processed"] == 2
    assert entry["report"]["looped"] == 2


def test_start_batch_records_error_status(session, monkeypatch):
    _seed(session)
    monkeypatch.setattr(runs_mod, "run_batch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rid = new_run_id()
    start_batch(rid, lambda: session, sync=False)
    assert BATCH_RUNS[rid]["status"] == "error"
    assert "boom" in BATCH_RUNS[rid]["error"]


def test_batch_run_background_returns_202_and_status(client, session):
    _seed(session)
    resp = client.post("/batch/run?background=true&sync=false")
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert run_id
    # TestClient runs the background task before returning; status should be queryable
    status = client.get(f"/batch/runs/{run_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"running", "completed"}


def test_batch_run_sync_still_returns_200(client, session):
    _seed(session)
    resp = client.post("/batch/run?sync=false")
    assert resp.status_code == 200
    assert resp.json()["processed"] == 2


def test_batch_runs_unknown_id_404(client):
    assert client.get("/batch/runs/nope").status_code == 404
