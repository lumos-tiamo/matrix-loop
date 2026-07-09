from app.connectors.youtube import YouTubeConnector


def _acct(handle="@ninacrypto"):
    return type("A", (), {"handle": handle, "platform": "youtube"})()


def test_fetch_maps_channel_statistics_to_snapshot():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        return {"items": [{"statistics": {"subscriberCount": "12000", "viewCount": "3400000"}}]}
    conn = YouTubeConnector("YT_KEY", http_get=fake_get)
    res = conn.fetch(_acct("@ninacrypto"))
    assert res.tier == "api"
    assert res.snapshots == [{"followers": 12000, "views": 3400000}]
    assert "forHandle=ninacrypto" in captured["url"] and "key=YT_KEY" in captured["url"]


def test_fetch_hidden_subs_or_no_channel_yields_empty():
    conn = YouTubeConnector("K", http_get=lambda url, headers: {"items": []})
    assert conn.fetch(_acct()).snapshots == []
