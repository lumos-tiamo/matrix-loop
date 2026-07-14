from __future__ import annotations

import pytest

from app.image.canvas import CanvasImageProvider


def _provider(posts, gets):
    calls = {"posts": [], "gets": []}

    def http_post(url, headers, json):
        calls["posts"].append((url, json))
        return posts.pop(0)

    def http_get(url, headers):
        calls["gets"].append(url)
        return gets.pop(0)

    p = CanvasImageProvider(
        base_url="http://127.0.0.1:3000", output_dir="/tmp", public_base_url="http://host",
        http_post=http_post, http_get=http_get, poll_interval=0, max_wait=10, sleep=lambda s: None,
    )
    return p, calls


def test_text_to_image_submit_and_poll():
    posts = [{"batch_id": "b1", "jobs": [{"job_id": "J1", "status": "queued"}]}]
    gets = [
        {"status": "running", "artifacts": []},
        {"status": "succeeded", "artifacts": [
            {"kind": "image", "path": "/abs/out/x.png", "url": "/assets/output/x.png",
             "meta": {"mime": "image/png"}}]},
    ]
    p, calls = _provider(posts, gets)
    r = p.generate(prompt="a cyberpunk host")
    assert r.provider == "canvas"
    assert r.path == "/abs/out/x.png"
    assert r.mime == "image/png"
    assert r.metadata["job_id"] == "J1"
    # submit body shape
    url, body = calls["posts"][0]
    assert url.endswith("/api/jobs")
    job = body["jobs"][0]
    assert job["type"] == "text_to_image"
    assert job["provider"] == "modelscope"        # default model_provider
    assert "input_image" not in job


def test_refs_switch_to_image_to_image():
    posts = [{"jobs": [{"job_id": "J2"}]}]
    gets = [{"status": "succeeded", "artifacts": [{"kind": "image", "path": "/o/y.png"}]}]
    p, calls = _provider(posts, gets)
    p.generate(prompt="same character new pose", refs=["/assets/aurea_ref.png"])
    job = calls["posts"][0][1]["jobs"][0]
    assert job["type"] == "image_to_image"
    assert job["input_image"] == "/assets/aurea_ref.png"


def test_params_passthrough_and_provider_override():
    posts = [{"jobs": [{"job_id": "J3"}]}]
    gets = [{"status": "succeeded", "artifacts": [{"path": "/o/z.png"}]}]
    p, calls = _provider(posts, gets)
    p.generate(prompt="x", params={"provider": "jimeng", "model": "Z-Image", "size": "1024x1024",
                                    "filename": "ignored"})
    job = calls["posts"][0][1]["jobs"][0]
    assert job["provider"] == "jimeng"                       # override wins
    assert job["params"] == {"model": "Z-Image", "size": "1024x1024"}   # control keys dropped


def test_failed_job_raises():
    posts = [{"jobs": [{"job_id": "J4"}]}]
    gets = [{"status": "failed", "error": "no credentials"}]
    p, _ = _provider(posts, gets)
    with pytest.raises(RuntimeError, match="failed"):
        p.generate(prompt="x")


def test_timeout_raises():
    posts = [{"jobs": [{"job_id": "J5"}]}]
    gets = [{"status": "running", "artifacts": []} for _ in range(50)]
    p, _ = _provider(posts, gets)
    p.poll_interval = 1        # real interval so max_wait accounting engages
    p.max_wait = 2
    with pytest.raises(TimeoutError):
        p.generate(prompt="x")


def test_no_job_id_raises():
    posts = [{"jobs": []}]
    p, _ = _provider(posts, [])
    with pytest.raises(RuntimeError, match="no job_id"):
        p.generate(prompt="x")


def test_factory_canvas(monkeypatch):
    from app.config import settings
    from app.image.factory import resolve_image_provider

    monkeypatch.setattr(settings, "image_provider", "canvas")
    prov = resolve_image_provider()
    assert prov.name == "canvas"
    assert prov.base_url == "http://127.0.0.1:3000"
