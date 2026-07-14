from __future__ import annotations

import pytest

from app.video.runninghub import RunningHubClient, RunningHubVideoProvider


def _client(posts, uploads=None):
    """Build a client with a scripted sequence of POST responses."""
    calls = {"posts": [], "uploads": []}

    def http_post(url, headers, json):
        calls["posts"].append((url, json))
        return posts.pop(0)

    def http_upload(url, headers, file_bytes, filename, mime):
        calls["uploads"].append((url, filename, mime, len(file_bytes)))
        return (uploads or []).pop(0)

    c = RunningHubClient(api_key="k", http_post=http_post, http_upload=http_upload)
    return c, calls


def test_submit_returns_task_id():
    c, calls = _client([{"code": 0, "data": {"taskId": "T123"}}])
    tid = c.submit("alibaba/wan-2.6/image-to-video", {"imageUrl": "u", "prompt": "p"})
    assert tid == "T123"
    url, body = calls["posts"][0]
    assert url == "https://www.runninghub.cn/openapi/v2/alibaba/wan-2.6/image-to-video"
    assert body["imageUrl"] == "u"


def test_submit_raises_on_error_code():
    c, _ = _client([{"code": 412, "msg": "TOKEN_INVALID"}])
    with pytest.raises(RuntimeError, match="TOKEN_INVALID"):
        c.submit("x/y", {})


def test_poll_success_returns_urls():
    posts = [
        {"code": 0, "data": {"status": "RUNNING"}},
        {"code": 0, "data": {"status": "SUCCESS", "results": [{"url": "https://cdn/v.mp4"}]}},
    ]
    c, _ = _client(posts)
    urls = c.poll("T1", interval=0, max_wait=10, sleep=lambda s: None)
    assert urls == ["https://cdn/v.mp4"]


def test_poll_failed_raises():
    c, _ = _client([{"code": 0, "data": {"status": "FAILED", "errorMessage": "bad"}}])
    with pytest.raises(RuntimeError, match="FAILED"):
        c.poll("T1", interval=0, max_wait=10, sleep=lambda s: None)


def test_poll_times_out():
    posts = [{"code": 0, "data": {"status": "RUNNING"}} for _ in range(50)]
    c, _ = _client(posts)
    with pytest.raises(TimeoutError):
        c.poll("T1", interval=1, max_wait=2, sleep=lambda s: None)


def test_provider_uploads_local_image_then_animates(tmp_path):
    img = tmp_path / "aurea.png"
    img.write_bytes(b"\x89PNG-fake")
    posts = [
        {"code": 0, "data": {"taskId": "T9"}},                                   # submit
        {"code": 0, "data": {"status": "SUCCESS", "results": ["https://cdn/out.mp4"]}},  # poll
    ]
    uploads = [{"code": 0, "data": {"download_url": "https://cdn/aurea.png"}}]
    client, calls = _client(posts, uploads)
    prov = RunningHubVideoProvider(
        client=client, model="wan", output_dir=str(tmp_path),
        public_base_url="http://host", http_get=lambda u: b"MP4BYTES",
        poll_interval=0, max_wait=10,
    )
    r = prov.generate(script="Aurea explains airdrops", brief=None,
                      params={"image_path": str(img), "duration": "5"})
    assert r.provider == "runninghub"
    assert r.dedup_key == "rh:T9"
    assert calls["uploads"][0][1] == "aurea.png"                 # uploaded the still
    _, body = calls["posts"][0]
    assert body["imageUrl"] == "https://cdn/aurea.png"           # used uploaded url
    assert body["resolution"] == "1080p"
    assert r.media_url == f"http://host/videos/{r.media_url.split('/')[-1]}"
    assert (tmp_path / r.media_url.split("/")[-1]).read_bytes() == b"MP4BYTES"


def test_provider_hailuo_payload_shape(tmp_path):
    posts = [
        {"code": 0, "data": {"taskId": "T"}},
        {"code": 0, "data": {"status": "SUCCESS", "results": ["https://cdn/o.mp4"]}},
    ]
    client, calls = _client(posts, [])
    prov = RunningHubVideoProvider(client=client, model="hailuo", output_dir=str(tmp_path),
                                   http_get=lambda u: b"X", poll_interval=0)
    prov.generate(script="s", brief=None, params={"image_url": "https://x/a.png", "duration": "10"})
    _, body = calls["posts"][0]
    assert body["imageUrl"] == "https://x/a.png"      # no upload — url passed straight through
    assert body["duration"] == "10"
    assert "enablePromptExpansion" in body
    assert not calls["uploads"]


def test_provider_requires_image(tmp_path):
    client, _ = _client([])
    prov = RunningHubVideoProvider(client=client, output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="image_url"):
        prov.generate(script="s", brief=None, params={})


def test_factory_runninghub_without_key_falls_back(monkeypatch):
    from app.config import settings
    from app.video.factory import resolve_video_provider

    monkeypatch.setattr(settings, "video_provider", "runninghub")
    monkeypatch.setattr(settings, "runninghub_api_key", None)
    assert resolve_video_provider().name == "fake"


def test_factory_runninghub_with_key(monkeypatch):
    from app.config import settings
    from app.video.factory import resolve_video_provider

    monkeypatch.setattr(settings, "video_provider", "runninghub")
    monkeypatch.setattr(settings, "runninghub_api_key", "k")
    prov = resolve_video_provider()
    assert prov.name == "runninghub"
