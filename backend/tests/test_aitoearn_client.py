from app.connectors.aitoearn_client import AiToEarnClient, to_aitoearn_platform


def test_platform_mapping():
    assert to_aitoearn_platform("xiaohongshu") == "xhs"
    assert to_aitoearn_platform("weixin_video") == "wxSph"
    assert to_aitoearn_platform("weixin_gzh") == "wxGzh"
    assert to_aitoearn_platform("douyin") == "douyin"
    assert to_aitoearn_platform("unknown") == "unknown"


def test_account_analytics_builds_url_and_auth():
    calls = {}
    def fake_get(url, headers):
        calls["url"] = url; calls["headers"] = headers
        return {"metrics": {"fansCount": 500}}
    c = AiToEarnClient("http://host:8080/api/v2/", "KEY", http_get=fake_get)
    out = c.account_analytics("acc_1")
    assert out == {"metrics": {"fansCount": 500}}
    assert calls["url"] == "http://host:8080/api/v2/channels/accounts/acc_1/analytics"
    assert calls["headers"]["x-api-key"] == "KEY"


def test_list_accounts_filters_types():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return {"total": 0, "list": []}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_get=fake_get)
    c.list_accounts(types=["xhs", "douyin"])
    assert "types%5B%5D=xhs" in seen["url"] and "types%5B%5D=douyin" in seen["url"]
