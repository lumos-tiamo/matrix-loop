import app.api.routes as routes
from app.models import Account
from app.connectors.base import ConnectorResult


def test_sync_manual_platform_returns_422(client, session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc)
    session.commit()
    resp = client.post(f"/accounts/{acc.id}/sync")
    assert resp.status_code == 422


def test_sync_happy_path(client, session, monkeypatch):
    acc = Account(platform="twitter", handle="@a")
    session.add(acc)
    session.commit()

    class FakeConnector:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 777}], content=[])

    monkeypatch.setattr(routes, "resolve_connector", lambda platform, cfg=None: (FakeConnector(), "api"))
    resp = client.post(f"/accounts/{acc.id}/sync")
    assert resp.status_code == 200
    assert resp.json()["snapshots_created"] == 1
    assert resp.json()["tier"] == "api"


def test_sync_404(client):
    assert client.post("/accounts/99999/sync").status_code == 404
