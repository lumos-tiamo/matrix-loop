"""TDD: /media StaticFiles mount is present and /health still works."""
from __future__ import annotations


def test_health_still_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_media_mount_exists():
    from app.main import app

    assert any(
        getattr(r, "path", "") == "/media" for r in app.routes
    ), "Expected a /media mount in app.routes"
