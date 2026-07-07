from app.models import Account
from app.connectors.x import XConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector


def test_x_connector_parses_public_metrics():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        captured["headers"] = headers
        return {"data": {"username": "a", "public_metrics": {"followers_count": 9001, "tweet_count": 42}}}

    conn = XConnector("BEARER", http_get=fake_get)
    result = conn.fetch(Account(platform="twitter", handle="@a"))
    assert result.tier == "api"
    assert result.snapshots == [{"followers": 9001}]
    assert "by/username/a" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer BEARER"


def test_scrapecreators_connector_parses_followers():
    def fake_get(url, headers):
        assert headers["x-api-key"] == "KEY"
        return {"followers": 55000}

    conn = ScrapeCreatorsConnector("KEY", "tiktok", http_get=fake_get)
    result = conn.fetch(Account(platform="tiktok", handle="@b"))
    assert result.tier == "scrape"
    assert result.snapshots == [{"followers": 55000}]


def test_x_connector_handles_missing_metrics():
    conn = XConnector("t", http_get=lambda url, headers: {"data": {}})
    result = conn.fetch(Account(platform="twitter", handle="@c"))
    assert result.snapshots == []
