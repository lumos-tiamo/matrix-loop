from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from app.video.waoowaoo_broll import WaoowaooBrollProvider

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class _FakeWaoowaoo:
    """A stateful in-memory double for waoowaoo's HTTP API. Records calls and advances
    panel state (imageUrl) once regenerate-panel-image has been posted, so the provider's
    resource-state polling terminates without a network or real backend. Video is NOT a
    waoowaoo call in this design (it goes to SiliconFlow), so there's no video endpoint."""

    def __init__(self, *, panels=2, fail_task=False):
        self.calls: list[tuple[str, str]] = []
        self._panel_ids = [f"panel{i}" for i in range(panels)]
        self._images = False
        self._fail_task = fail_task

    def post(self, url: str, headers: dict, json: dict) -> dict:
        path = url.replace("http://x", "")
        self.calls.append(("POST", path))
        assert headers.get("x-internal-task-token") == "tok"
        assert headers.get("x-internal-user-id") == "user1"
        if path == "/api/projects":
            return {"project": {"id": "proj1"}}
        if path.endswith("/episodes"):
            return {"episode": {"id": "ep1"}}
        if path.endswith("/story-to-script-stream"):
            return {"taskId": "task-s2s"}
        if path.endswith("/script-to-storyboard-stream"):
            return {"taskId": "task-s2b"}
        if path.endswith("/regenerate-panel-image"):
            self._images = True
            return {"taskId": "task-img"}
        raise AssertionError(f"unexpected POST {path}")

    def get(self, url: str, headers: dict) -> dict:
        path = url.replace("http://x", "")
        self.calls.append(("GET", path))
        if path.startswith("/api/tasks/"):
            return {"task": {"status": "failed", "errorMessage": "boom"}} if self._fail_task \
                else {"task": {"status": "completed"}}
        if "/episodes/" in path:
            panels = []
            for i, pid in enumerate(self._panel_ids):
                p = {"id": pid, "panelIndex": i}
                if self._images:
                    p["imageUrl"] = f"/media/img{i}.png"
                    p["videoPrompt"] = f"motion {i}"
                panels.append(p)
            return {"episode": {"storyboards": [{"panels": panels}]}}
        raise AssertionError(f"unexpected GET {path}")


def _provider(fake, **kw):
    return WaoowaooBrollProvider(
        base_url="http://x",
        internal_token="tok",
        user_id="user1",
        sf_api_key="sf-test",
        http_post=fake.post,
        http_get=fake.get,
        sleep=lambda _s: None,
        **kw,
    )


def test_orchestration_sequence_returns_broll(monkeypatch, tmp_path):
    fake = _FakeWaoowaoo(panels=2)
    prov = _provider(fake, output_dir=str(tmp_path))
    # isolate orchestration from SiliconFlow + ffmpeg
    monkeypatch.setattr(prov, "_panel_clip_urls", lambda pid, eid, ids: ["c0", "c1"])
    monkeypatch.setattr(prov, "_concat_clips",
                        lambda urls, eid: (str(tmp_path / f"{eid}.mp4"), 12.5))

    res = prov.generate(script="Bitcoin halving explained.", brief=None, params={})

    assert res.provider == "waoowaoo"
    assert res.metadata["episode_id"] == "ep1"
    assert res.metadata["panel_count"] == 2
    assert res.duration == 12.5
    posts = [p for (m, p) in fake.calls if m == "POST"]
    assert posts[0] == "/api/projects"
    assert posts[1].endswith("/episodes")
    assert posts[2].endswith("/story-to-script-stream")
    assert posts[3].endswith("/script-to-storyboard-stream")
    assert sum(1 for p in posts if p.endswith("/regenerate-panel-image")) == 2
    # video is NOT a waoowaoo call anymore
    assert not any(p.endswith("/generate-video") for p in posts)
    assert not any(p.endswith("/video-urls") for p in posts)


def test_panel_clip_urls_calls_siliconflow_per_panel_in_order(monkeypatch):
    fake = _FakeWaoowaoo(panels=3)
    fake._images = True  # panels already carry imageUrl
    prov = _provider(fake)
    monkeypatch.setattr(prov, "_fetch_image_datauri", lambda u: f"data::{u}")
    seen = []
    monkeypatch.setattr(prov, "_siliconflow_i2v",
                        lambda img, prompt: seen.append((img, prompt)) or f"clip::{img}")

    urls = prov._panel_clip_urls("proj1", "ep1", ["panel0", "panel1", "panel2"])

    assert urls == ["clip::data::/media/img0.png", "clip::data::/media/img1.png",
                    "clip::data::/media/img2.png"]
    assert [p for _, p in seen] == ["motion 0", "motion 1", "motion 2"]  # video_prompt used, in order


def test_task_failure_falls_back_to_still():
    fake = _FakeWaoowaoo(fail_task=True)

    class _Still:
        name = "still"
        def generate(self, *, script, brief, params):
            from app.video.base import VideoResult
            return VideoResult(media_url="/tmp/still.png", duration=0.0, cost=0.0,
                               provider="still", dedup_key="still")

    prov = _provider(fake, fallback_visual=_Still())
    res = prov.generate(script="x", brief=None, params={})
    assert res.provider == "still"  # degraded, loop not stalled


def test_missing_sf_key_falls_back():
    fake = _FakeWaoowaoo()

    class _Still:
        name = "still"
        def generate(self, *, script, brief, params):
            from app.video.base import VideoResult
            return VideoResult(media_url="/tmp/s.png", duration=0.0, cost=0.0,
                               provider="still", dedup_key="s")

    prov = WaoowaooBrollProvider(base_url="http://x", internal_token="tok", user_id="user1",
                                 sf_api_key="", http_post=fake.post, http_get=fake.get,
                                 sleep=lambda _s: None, fallback_visual=_Still())
    assert prov.generate(script="x", brief=None, params={}).provider == "still"


def test_no_fallback_reraises():
    fake = _FakeWaoowaoo(fail_task=True)
    prov = _provider(fake)  # no fallback_visual
    with pytest.raises(RuntimeError):
        prov.generate(script="x", brief=None, params={})


def test_build_story_uses_writer_then_falls_back_to_script():
    fake = _FakeWaoowaoo()
    prov = _provider(fake, story_writer=lambda s, b: "A trader named Kai...")
    assert prov._build_story("narration", None) == "A trader named Kai..."

    prov_boom = _provider(fake, story_writer=lambda s, b: (_ for _ in ()).throw(ValueError("x")))
    assert prov_boom._build_story("narration", None) == "narration"

    prov_none = _provider(fake)
    assert prov_none._build_story("narration", None) == "narration"


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe required for real concat")
def test_concat_produces_playable_mp4(monkeypatch, tmp_path):
    clips = []
    for i, size in enumerate(("320x240", "640x360")):
        c = str(tmp_path / f"src{i}.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"testsrc=size={size}:duration=1:rate=30", "-pix_fmt", "yuv420p", c],
                       capture_output=True)
        clips.append(c)

    fake = _FakeWaoowaoo()
    prov = _provider(fake, output_dir=str(tmp_path), resolution=(360, 640))
    monkeypatch.setattr(prov, "_download", lambda url, dest: shutil.copy(clips.pop(0), dest))

    out, duration = prov._concat_clips(["u0", "u1"], "epX")
    assert os.path.exists(out)
    assert duration > 1.5
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                            "-of", "default=nw=1", out], capture_output=True, text=True)
    assert "codec_type=video" in probe.stdout
    assert "width=360" in probe.stdout and "height=640" in probe.stdout
