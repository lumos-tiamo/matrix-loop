from app.connectors.aitoearn_client import AiToEarnClient


def test_publish_flow_posts_payload_with_auth():
    seen = {}
    def fake_post(url, headers, json):
        seen["url"] = url; seen["headers"] = headers; seen["json"] = json
        return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_post=fake_post)
    out = c.publish_flow({"content": {"media": []}, "items": []})
    assert out["flowId"] == "f1"
    assert seen["url"] == "http://host/api/v2/channels/publish/flows"
    assert seen["headers"]["x-api-key"] == "KEY"
    assert seen["json"]["content"] == {"media": []}


def test_flow_status_gets_by_id():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return {"flowId": "f1", "tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_get=fake_get)
    out = c.flow_status("f1")
    assert out["tasks"][0]["platformWorkId"] == "w9"
    assert seen["url"] == "http://host/api/v2/channels/publish/flows/f1"
