from datetime import datetime, timezone

from app.models import Account, Snapshot

CSV = """platform,handle,ts,followers,views,engagement_rate,hit_rate,conversions
xiaohongshu,@imp,2026-07-01T00:00:00+00:00,100000,0,0.05,0,0
xiaohongshu,@imp,2026-07-06T00:00:00+00:00,110000,0,0.05,0,0
"""


def test_import_snapshots_endpoint(client, session):
    resp = client.post("/import/snapshots", json={"csv": CSV})
    assert resp.status_code == 200
    assert resp.json() == {"accounts_created": 1, "snapshots_created": 2}
    assert session.query(Account).filter_by(handle="@imp").count() == 1


def test_trigger_loop_endpoint(client, session):
    acc = Account(platform="x", handle="@loop", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()

    resp = client.post(f"/accounts/{acc.id}/loop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["evaluation"]["composite_score"] == 100.0
    assert len(body["recommendations"]) >= 1


def test_trigger_loop_404(client):
    assert client.post("/accounts/99999/loop").status_code == 404
