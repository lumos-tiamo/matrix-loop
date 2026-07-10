from app.connectors.aitoearn_client import AiToEarnClient


def test_submit_video_posts_to_ai_base_with_auth():
    seen = {}
    def fake_post(url, headers, json):
        seen["url"] = url; seen["headers"] = headers; seen["json"] = json
        return {"data": {"id": "task1", "status": "submitted"}, "code": 0}
    c = AiToEarnClient("http://h/api/v2", "KEY", http_post=fake_post, ai_base_url="http://h/api/ai")
    out = c.submit_video({"model": "seedance-1-pro", "prompt": "a coin", "ratio": "9:16", "duration": 5})
    assert out["data"]["id"] == "task1"
    assert seen["url"] == "http://h/api/ai/video/generations"
    assert seen["headers"]["x-api-key"] == "KEY"
    assert seen["json"]["model"] == "seedance-1-pro"


def test_video_task_gets_status_by_id():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return {"data": {"id": "task1", "status": "success", "videoUrl": "https://cdn/v.mp4"}, "code": 0}
    c = AiToEarnClient("http://h/api/v2", "KEY", http_get=fake_get, ai_base_url="http://h/api/ai")
    out = c.video_task("task1")
    assert out["data"]["videoUrl"] == "https://cdn/v.mp4"
    assert seen["url"] == "http://h/api/ai/video/generations/task1"
