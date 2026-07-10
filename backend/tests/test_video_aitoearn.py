import pytest
from app.video.aitoearn import AiToEarnVideoProvider


class _Client:
    def __init__(self, submit, tasks):
        self._submit = submit; self._tasks = list(tasks); self.i = 0; self.posted = None
    def submit_video(self, payload): self.posted = payload; return self._submit
    def video_task(self, task_id):
        r = self._tasks[min(self.i, len(self._tasks) - 1)]; self.i += 1; return r


def _brief():
    return type("B", (), {"main_direction": "web3", "sub_niches": ["defi"], "persona": "Nina", "target_seconds": 50})()


def test_generate_submits_and_polls_to_success():
    client = _Client(
        {"data": {"id": "t1", "status": "submitted"}, "code": 0},
        [{"data": {"status": "in_progress"}}, {"data": {"status": "success", "videoUrl": "https://cdn/v.mp4", "coverUrl": "https://cdn/c.jpg"}}],
    )
    p = AiToEarnVideoProvider(client, model="seedance-1-pro", sleep=lambda s: None)
    res = p.generate(script="Airdrops are back. Here's how...", brief=_brief(), params={})
    assert res.provider == "aitoearn" and res.media_url == "https://cdn/v.mp4"
    assert res.dedup_key == "t1"
    assert client.posted["model"] == "seedance-1-pro" and client.posted["prompt"]


def test_generate_raises_on_failure_status():
    client = _Client(
        {"data": {"id": "t2", "status": "submitted"}},
        [{"data": {"status": "failure", "error": {"message": "nsfw"}}}],
    )
    p = AiToEarnVideoProvider(client, model="m", sleep=lambda s: None)
    with pytest.raises(RuntimeError) as e:
        p.generate(script="x", brief=_brief(), params={})
    assert "nsfw" in str(e.value)


def test_generate_raises_on_missing_task_id():
    client = _Client({"data": {}, "code": 1, "message": "bad model"}, [{}])
    p = AiToEarnVideoProvider(client, model="m", sleep=lambda s: None)
    with pytest.raises(RuntimeError):
        p.generate(script="x", brief=_brief(), params={})


def test_generate_times_out():
    client = _Client(
        {"data": {"id": "t3", "status": "submitted"}},
        [{"data": {"status": "in_progress"}}],
    )
    p = AiToEarnVideoProvider(client, model="m", sleep=lambda s: None, poll_attempts=2)
    with pytest.raises(RuntimeError) as e:
        p.generate(script="x", brief=_brief(), params={})
    assert "timed out" in str(e.value)


def test_visual_prompt_override_via_params():
    client = _Client({"data": {"id": "t4", "status": "submitted"}},
                     [{"data": {"status": "success", "videoUrl": "https://cdn/v.mp4"}}])
    p = AiToEarnVideoProvider(client, model="m", sleep=lambda s: None)
    p.generate(script="s", brief=_brief(), params={"visual_prompt": "explicit prompt X", "duration": 8, "ratio": "16:9"})
    assert client.posted["prompt"] == "explicit prompt X"
    assert client.posted["duration"] == 8 and client.posted["ratio"] == "16:9"
