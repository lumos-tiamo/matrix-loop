from app.connectors.instagram import InstagramConnector


def _acct(handle="@ninaweb3"):
    return type("A", (), {"handle": handle, "platform": "instagram"})()


def test_fetch_maps_business_discovery_to_snapshot():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        return {"business_discovery": {"followers_count": 8800, "media_count": 120, "id": "1"}}
    conn = InstagramConnector("IG_TOKEN", "ig_biz_1", http_get=fake_get)
    res = conn.fetch(_acct("@ninaweb3"))
    assert res.tier == "api"
    assert res.snapshots == [{"followers": 8800}]
    assert "ig_biz_1" in captured["url"]
    assert "business_discovery.username(ninaweb3)" in captured["url"]
    assert "access_token=IG_TOKEN" in captured["url"]


def test_fetch_no_discovery_yields_empty():
    conn = InstagramConnector("T", "b", http_get=lambda url, headers: {})
    assert conn.fetch(_acct()).snapshots == []
