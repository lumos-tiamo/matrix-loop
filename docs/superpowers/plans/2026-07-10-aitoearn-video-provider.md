# AiToEarn Video Provider (maximal reuse) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Reuse AiToEarn's full video-generation pipeline over HTTP — add an `AiToEarnVideoProvider` behind the existing `VideoProvider` seam that submits to AiToEarn's async video API (`POST /api/ai/video/generations`), polls (`GET /api/ai/video/generations/:id`), and returns the hosted `videoUrl`. This reuses AiToEarn's multi-provider video-gen (Volcengine/Seedance, Sora, Grok, DashScope) with server-side keys — matrix-loop supplies no model keys and bypasses the local 即梦-CLI tier gate.

**Architecture:** Extend the existing `AiToEarnClient` (same `x-api-key` auth) with an `ai_base_url` + `submit_video`/`video_task` methods (the AI service is under `/api/ai/`, a different nginx route than `/api/v2` channels — hence a separate base). `AiToEarnVideoProvider` mirrors the existing `SeedanceVideoProvider` shape (injectable client/sleep, bounded poll, graceful failure) and returns `VideoResult(media_url=videoUrl, provider="aitoearn", ...)`. Config-gated via `video_provider="aitoearn"`. Fully fake-tested (injected HTTP/client) — no live AiToEarn needed for tests.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, pytest. Backend Python: `backend/.venv/bin/python` from `backend/`.

Preconditions: on `main`, clean, `git checkout -b feat/aitoearn-video`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 265 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

Reference (existing, mirror these): `backend/app/connectors/aitoearn_client.py` (AiToEarnClient: injected http_get/http_post, `_headers` x-api-key, publish_flow/flow_status), `backend/app/video/seedance.py` (provider: _build_prompt, submit→poll→VideoResult, bounded poll, graceful errors), `backend/app/video/factory.py` (resolve_video_provider), `backend/app/video/base.py` (VideoResult), `backend/app/config.py`.

---

### Task 1: Config + AiToEarnClient video methods

**Files:** `backend/app/config.py`, `backend/app/connectors/aitoearn_client.py`; Test `backend/tests/test_aitoearn_video_client.py` (create).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_aitoearn_video_client.py -q`

- [ ] **Step 3: Config** — in `backend/app/config.py` `Settings`, add:

```python
    aitoearn_ai_base_url: str | None = None       # AiToEarn AI service base, e.g. http://127.0.0.1:8080/api/ai
    aitoearn_video_model: str = "seedance-1-pro"  # model routed by AiToEarn (Volcengine/Seedance/Sora/...)
```

- [ ] **Step 4: Extend AiToEarnClient** — in `backend/app/connectors/aitoearn_client.py`:
  - Add `ai_base_url: str | None = None` to `__init__` and store `self.ai_base_url = (ai_base_url or "").rstrip("/")`.
  - Add methods:

```python
    def submit_video(self, payload: dict) -> dict:
        url = f"{self.ai_base_url}/video/generations"
        return self._http_post(url, self._headers(), payload) or {}

    def video_task(self, task_id: str) -> dict:
        url = f"{self.ai_base_url}/video/generations/{task_id}"
        return self._http_get(url, self._headers()) or {}
```

- [ ] **Step 5: Run — expect PASS.** Confirm existing aitoearn_client tests still pass (`ai_base_url` is an optional new kwarg).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/config.py backend/app/connectors/aitoearn_client.py backend/tests/test_aitoearn_video_client.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): AiToEarn AI video methods (submit_video/video_task) + ai_base_url\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: `AiToEarnVideoProvider` + factory wiring

**Files:** Create `backend/app/video/aitoearn.py`; Modify `backend/app/video/factory.py`; Test `backend/tests/test_video_aitoearn.py` (create), extend `backend/tests/test_video_factory.py`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_video_aitoearn.py`:

```python
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
```

Extend `backend/tests/test_video_factory.py`:

```python
def test_resolve_returns_aitoearn_when_configured(monkeypatch):
    from app.config import settings
    from app.video.aitoearn import AiToEarnVideoProvider
    monkeypatch.setattr(settings, "video_provider", "aitoearn", raising=False)
    monkeypatch.setattr(settings, "aitoearn_ai_base_url", "http://h/api/ai", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    from app.video.factory import resolve_video_provider
    assert isinstance(resolve_video_provider(), AiToEarnVideoProvider)
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `backend/app/video/aitoearn.py`**

```python
from __future__ import annotations

import logging

from app.video.base import VideoResult

logger = logging.getLogger(__name__)


class AiToEarnVideoProvider:
    """Reuse AiToEarn's video-generation pipeline over HTTP (multi-provider: Volcengine/Seedance,
    Sora, Grok, DashScope — server-side keys). Submits an async task, polls to completion, returns
    the hosted video URL. Injectable client/sleep for tests.

    NOTE: generate() is synchronous and blocks up to poll_attempts*poll_interval seconds; a fully
    async job model is a follow-up (same constraint as the other providers)."""

    name = "aitoearn"

    def __init__(self, client, *, model="seedance-1-pro", poll_attempts=40, poll_interval=5, sleep=None):
        self.client = client
        self.model = model
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval
        import time
        self._sleep = sleep or time.sleep

    def _build_prompt(self, script, brief, params):
        if params and params.get("visual_prompt"):
            return params["visual_prompt"]
        niches = "、".join(getattr(brief, "sub_niches", None) or []) if brief else ""
        direction = getattr(brief, "main_direction", "") if brief else ""
        head = (script or "").strip().replace("\n", " ")[:200]
        bits = [b for b in [direction, niches] if b]
        style = ("Short-form vertical (9:16) b-roll for a "
                 + (", ".join(bits) if bits else "content") + " video. ")
        return style + ("Scene: " + head if head else "cinematic, dynamic, on-brand")

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        payload = {
            "model": self.model,
            "prompt": self._build_prompt(script, brief, params),
            "ratio": params.get("ratio", "9:16"),
            "duration": params.get("duration", 5),
        }
        resp = self.client.submit_video(payload) or {}
        data = resp.get("data") or {}
        task_id = data.get("id")
        if not task_id:
            raise RuntimeError(f"aitoearn video submit failed: {resp.get('message') or resp}")
        result = self._poll(task_id)
        video_url = result.get("videoUrl")
        if not video_url:
            raise RuntimeError(f"aitoearn video succeeded but no videoUrl (task {task_id})")
        return VideoResult(
            media_url=video_url,
            duration=float(payload["duration"]) if payload.get("duration") else 5.0,
            cost=float(result.get("cost") or 1.0),
            provider=self.name,
            dedup_key=str(task_id),
            metadata={"task_id": task_id, "model": self.model, "cover_url": result.get("coverUrl")},
        )

    def _poll(self, task_id: str) -> dict:
        for attempt in range(self._poll_attempts):
            resp = self.client.video_task(task_id) or {}
            data = resp.get("data") or {}
            status = data.get("status")
            logger.debug("aitoearn video poll %d/%d task=%s status=%s",
                         attempt + 1, self._poll_attempts, task_id, status)
            if status == "success":
                return data
            if status == "failure":
                err = (data.get("error") or {}).get("message") or "unknown"
                raise RuntimeError(f"aitoearn video generation failed: {err}")
            if attempt < self._poll_attempts - 1:
                self._sleep(self._poll_interval)
        raise RuntimeError(f"aitoearn video generation timed out for task {task_id}")
```

- [ ] **Step 4: Wire the factory** — in `backend/app/video/factory.py`, add an `aitoearn` branch (before the seedance/fake fallback):

```python
def resolve_video_provider():
    from app.config import settings
    try:
        if settings.video_provider == "aitoearn" and settings.aitoearn_ai_base_url and settings.aitoearn_api_key:
            from app.connectors.aitoearn_client import AiToEarnClient
            from app.video.aitoearn import AiToEarnVideoProvider
            client = AiToEarnClient(settings.aitoearn_base_url or "", settings.aitoearn_api_key,
                                    ai_base_url=settings.aitoearn_ai_base_url)
            return AiToEarnVideoProvider(client, model=settings.aitoearn_video_model)
        if settings.video_provider == "seedance":
            from app.video.seedance import SeedanceVideoProvider
            return SeedanceVideoProvider(binary=settings.dreamina_bin, model=settings.seedance_model,
                                         output_dir=settings.video_output_dir, public_base_url=settings.public_base_url)
    except Exception as exc:  # noqa: BLE001 - never break the loop on a misconfigured provider
        logger.warning("video provider init failed (%s: %s); falling back to fake", exc.__class__.__name__, exc)
    from app.video.fake import FakeVideoProvider
    return FakeVideoProvider()
```

(Preserve the existing seedance construction args exactly as they currently are — read the current factory first and keep its seedance branch verbatim; only ADD the aitoearn branch above it and keep the try/except + fake fallback. If the current factory has no logger, add `import logging; logger = logging.getLogger(__name__)`.)

- [ ] **Step 5: Run — expect PASS** (`tests/test_video_aitoearn.py tests/test_video_factory.py`).

- [ ] **Step 6: Full suite** — `cd backend && ./.venv/bin/python -m pytest -q` — all pass (265 + new).

- [ ] **Step 7: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/aitoearn.py backend/app/video/factory.py backend/tests/test_video_aitoearn.py backend/tests/test_video_factory.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): AiToEarnVideoProvider reuses AiToEarn video-gen over HTTP (submit/poll)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Final review over the branch; `superpowers:finishing-a-development-branch` → merge `main` (`--no-ff`).
- Update `docs/DELIVERY.md`: video provider options are now `fake | seedance | aitoearn`; **`aitoearn` is the recommended real path** (reuses AiToEarn's server-side Volcengine/Seedance/Sora — no local 即梦 tier gate). To enable: `MATRIXLOOP_VIDEO_PROVIDER=aitoearn`, `MATRIXLOOP_AITOEARN_AI_BASE_URL=http://<host>:8080/api/ai`, `MATRIXLOOP_AITOEARN_API_KEY=<key>`, `MATRIXLOOP_AITOEARN_VIDEO_MODEL=<model from GET /api/ai/models/video/generation>`.
- Live smoke (manual, needs AiToEarn running with a configured video channel): set the env, generate a video via `/accounts/{id}/generate-video`, confirm a real `videoUrl` comes back.

## Deferred / notes

- AiToEarn video-gen is model-based text/image-to-video (no TTS/avatar/ffmpeg faceless assembly) — same shape as our Seedance provider. Faceless voiceover assembly (script→TTS+captions+stitch) remains a separate future provider if desired.
- Async job model (non-blocking submit/poll across requests) is a shared follow-up for all video providers.
- `duration` here is the CLIP length (default 5s), distinct from `ChannelBrief.target_seconds` (script/voiceover length).

## Self-review

- Coverage: config + client video methods (T1), provider + factory (T2). Reuses AiToEarnClient auth/http + mirrors SeedanceVideoProvider structure.
- Type consistency: `VideoProvider.generate(*, script, brief, params) -> VideoResult` honored; factory returns the seam type; `submit_video`/`video_task` match provider usage; `ai_base_url` optional kwarg keeps existing AiToEarnClient callers working.
- No placeholders: full code + commands.
