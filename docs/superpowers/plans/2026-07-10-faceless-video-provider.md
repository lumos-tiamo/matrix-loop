# FacelessVideoProvider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `faceless` video形态 to matrix-loop that composes a vertical 口播 short video from a script — TTS voiceover + an inner clip-provider's b-roll + burned ASS captions, stitched by ffmpeg — following the existing pluggable-seam + fake-fallback pattern so it is testable and deliverable with no external keys.

**Architecture:** Two new seams. (1) `TTSProvider` (`app/video/tts/`): `FakeTTSProvider` (offline, `wave` stdlib silence), `SayTTSProvider` (macOS `say`), `OpenAITTSProvider` (`/v1/audio/speech`, reuses relay key), `resolve_tts_provider` factory. (2) `FacelessVideoProvider` (`app/video/faceless.py`) implements the existing `VideoProvider` protocol, so the governor/guardrails/factory reuse it unchanged; it wraps an inner clip provider (aitoearn/seedance/fake) for the background. Captions live in `app/video/captions.py`; a shared `app/video/ffmpeg_util.py` holds `ffprobe_duration`.

**Tech Stack:** Python 3.13 (`backend/.venv/bin/python`, run from `backend/`), pytest, ffmpeg 8.1.1 + ffprobe (present), macOS `say` (present), httpx.

**Preconditions:** On branch `feat/faceless-video`, clean. Baseline: backend **273** tests green. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Reference spec: `docs/superpowers/specs/2026-07-10-faceless-video-provider-design.md`. **No new DB columns — no DB recreate needed.**

**File Structure:**
- Create `backend/app/video/ffmpeg_util.py` — `ffprobe_duration(path, run=None)` shared helper.
- Create `backend/app/video/tts/__init__.py`, `base.py` (`TTSResult` + `TTSProvider`), `fake.py`, `say.py`, `openai.py`, `factory.py`.
- Create `backend/app/video/captions.py` — `chunk_caption`, `build_ass`.
- Create `backend/app/video/faceless.py` — `FacelessVideoProvider`.
- Modify `backend/app/config.py` — TTS + faceless settings.
- Modify `backend/app/video/factory.py` — `faceless` branch + `_resolve_clip_provider` helper.

---

### Task 1: Config + ffmpeg_util + TTS base + FakeTTSProvider

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/video/ffmpeg_util.py`
- Create: `backend/app/video/tts/__init__.py`, `backend/app/video/tts/base.py`, `backend/app/video/tts/fake.py`
- Test: `backend/tests/test_tts.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_tts.py`:

```python
from __future__ import annotations

import wave

from app.video.tts.base import TTSResult
from app.video.tts.fake import FakeTTSProvider


def test_fake_tts_duration_from_word_count(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path))
    # 27 words -> 27/2.7 = 10.0s
    text = " ".join(["word"] * 27)
    res = p.synthesize(text=text)
    assert isinstance(res, TTSResult)
    assert res.fmt == "wav"
    assert abs(res.duration_seconds - 10.0) < 0.01
    assert p.name == "fake"


def test_fake_tts_writes_playable_silence_wav(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path), rate=16000)
    res = p.synthesize(text="hello world here")   # 3 words -> max(1.0, 1.11) = 1.11s
    with wave.open(res.audio_path, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        frames = w.getnframes()
    assert abs(frames / 16000 - res.duration_seconds) < 0.05


def test_fake_tts_empty_text_min_duration(tmp_path):
    p = FakeTTSProvider(output_dir=str(tmp_path))
    res = p.synthesize(text="")
    assert res.duration_seconds == 1.0
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.tts'`.

- [ ] **Step 3: Create `backend/app/video/tts/__init__.py`** (empty file).

- [ ] **Step 4: Create `backend/app/video/tts/base.py`:**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TTSResult:
    audio_path: str
    duration_seconds: float
    fmt: str  # "wav" | "mp3"


class TTSProvider(Protocol):
    name: str

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult: ...
```

- [ ] **Step 5: Create `backend/app/video/tts/fake.py`:**

```python
from __future__ import annotations

import hashlib
import os
import wave

from app.video.tts.base import TTSResult


class FakeTTSProvider:
    """Deterministic offline TTS: writes N seconds of silence via the wave stdlib
    (no ffmpeg, no network). Duration derived from word count so downstream timing
    is realistic. Used for tests and as the last-resort factory fallback."""

    name = "fake"

    def __init__(self, *, output_dir="./data/videos", rate=16000):
        self._output_dir = os.path.abspath(output_dir)
        self._rate = int(rate)

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult:
        words = len((text or "").split())
        duration = max(1.0, round(words / 2.7, 2))
        os.makedirs(self._output_dir, exist_ok=True)
        digest = hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]
        path = os.path.join(self._output_dir, f"tts_fake_{digest}.wav")
        nframes = int(duration * self._rate)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self._rate)
            w.writeframes(b"\x00\x00" * nframes)
        return TTSResult(audio_path=path, duration_seconds=duration, fmt="wav")
```

- [ ] **Step 6: Create `backend/app/video/ffmpeg_util.py`** (shared probe used by say/openai/faceless in later tasks):

```python
from __future__ import annotations

import subprocess


def _default_run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr


def ffprobe_duration(path, run=None):
    """Return media duration in seconds via ffprobe. `run(cmd)->(rc,out,err)` is injectable for tests."""
    runner = run or _default_run
    rc, out, err = runner(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:np=1", path]
    )
    if rc != 0:
        raise RuntimeError(f"ffprobe failed rc={rc}: {(err or out or '').strip()[:200]}")
    try:
        return float((out or "").strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned non-numeric duration: {out!r}") from exc
```

- [ ] **Step 7: Modify `backend/app/config.py`** — after the line `aitoearn_video_model: str = "seedance-1-pro" ...` (line ~33) add:

```python
    # --- faceless 口播 video (TTS voiceover + inner clip b-roll + burned captions) ---
    tts_provider: str = "auto"            # auto | say | openai | fake
    tts_model: str = ""                   # e.g. "tts-1"; empty disables the openai TTS path
    tts_voice: str = "alloy"
    tts_base_url: str | None = None       # defaults to anthropic_base_url when empty
    tts_api_key: str | None = None        # defaults to anthropic_api_key when empty
    faceless_visual: str = "fake"         # aitoearn | seedance | fake — inner clip provider for b-roll
```

Also update the `video_provider` comment on line ~27 to: `# fake | seedance | aitoearn | faceless`.

- [ ] **Step 8: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts.py -q` (3 passed). Then full suite `./.venv/bin/python -m pytest -q` (still 273+ passing, config additions are additive).

- [ ] **Step 9: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/config.py backend/app/video/ffmpeg_util.py backend/app/video/tts/__init__.py backend/app/video/tts/base.py backend/app/video/tts/fake.py backend/tests/test_tts.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): TTSProvider seam + FakeTTSProvider + ffprobe util + faceless config\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Captions (chunk + ASS builder)

**Files:**
- Create: `backend/app/video/captions.py`
- Test: `backend/tests/test_captions.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_captions.py`:

```python
from __future__ import annotations

from app.video.captions import build_ass, chunk_caption


def test_chunk_splits_sentences_and_long_runs():
    chunks = chunk_caption("A. B C D E F G H.", max_words=6)
    assert chunks == ["A", "B C D E F G", "H"]


def test_chunk_empty_returns_empty():
    assert chunk_caption("") == []
    assert chunk_caption("   \n  ") == []


def test_build_ass_has_header_and_one_dialogue_per_chunk():
    ass = build_ass(["hello world", "second line here"], 10.0, resolution=(1080, 1920))
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert ass.count("Dialogue:") == 2


def test_build_ass_allocates_time_by_char_length():
    # two chunks, second is ~2x longer -> gets ~2x the time; first ends near 10*(len1/(len1+len2))
    ass = build_ass(["ab", "abcd"], 6.0)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(dialogues) == 2
    # first dialogue End timestamp field (index 2 in the comma-split after "Dialogue: ")
    first_end = dialogues[0].split(",")[2]
    assert first_end.startswith("0:00:02")  # 6 * 2/6 = 2.0s


def test_build_ass_empty_chunks_header_only():
    ass = build_ass([], 10.0)
    assert "[Script Info]" in ass
    assert "Dialogue:" not in ass
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_captions.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.captions'`.

- [ ] **Step 3: Create `backend/app/video/captions.py`:**

```python
from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def chunk_caption(text: str, *, max_words: int = 6) -> list[str]:
    """Split spoken text into short on-screen caption chunks (<= max_words words each),
    breaking first on sentence enders then on word count."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        words = sentence.split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i:i + max_words]).strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def _fmt_ass_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(chunks: list[str], total_seconds: float, *, resolution: tuple[int, int] = (1080, 1920)) -> str:
    """Build an ASS subtitle document. Each chunk's on-screen time is proportional to its
    character length so it tracks the narration pace. Empty chunks -> header only."""
    w, h = resolution
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,72,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        "4,1,2,60,60,180,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if chunks and total_seconds > 0:
        weights = [max(1, len(c)) for c in chunks]
        total_w = sum(weights)
        t = 0.0
        for chunk, wt in zip(chunks, weights):
            dur = total_seconds * (wt / total_w)
            start, end = t, t + dur
            t = end
            text = chunk.replace("\n", " ")
            lines.append(
                f"Dialogue: 0,{_fmt_ass_ts(start)},{_fmt_ass_ts(end)},Default,,0,0,0,,{text}"
            )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_captions.py -q` (5 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/captions.py backend/tests/test_captions.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): caption chunking + ASS subtitle builder\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: SayTTSProvider + OpenAITTSProvider

**Files:**
- Create: `backend/app/video/tts/say.py`, `backend/app/video/tts/openai.py`
- Test: `backend/tests/test_tts_providers.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_tts_providers.py`:

```python
from __future__ import annotations

import pytest

from app.video.tts.openai import OpenAITTSProvider
from app.video.tts.say import SayTTSProvider


class _RunRecorder:
    """Fake run(cmd)->(rc,out,err). Returns a canned ffprobe duration for ffprobe calls."""
    def __init__(self, duration="2.50"):
        self.calls = []
        self._duration = duration

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd and cmd[0] == "ffprobe":
            return 0, f"{self._duration}\n", ""
        return 0, "", ""


def test_say_builds_command_and_probes_duration(tmp_path):
    run = _RunRecorder(duration="3.00")
    p = SayTTSProvider(output_dir=str(tmp_path), run=run)
    res = p.synthesize(text="hello there friends")
    assert p.name == "say"
    assert res.fmt == "wav" and res.audio_path.endswith(".wav")
    assert res.duration_seconds == 3.0
    # say invoked with -f <textfile> -o <aiff>
    say_call = next(c for c in run.calls if c[0] == "say")
    assert "-f" in say_call and "-o" in say_call
    # ffmpeg aiff->wav invoked
    assert any(c[0] == "ffmpeg" for c in run.calls)


def test_say_raises_on_nonzero(tmp_path):
    def run(cmd):
        if cmd[0] == "say":
            return 1, "", "no voice"
        return 0, "", ""
    with pytest.raises(RuntimeError, match="say failed"):
        SayTTSProvider(output_dir=str(tmp_path), run=run).synthesize(text="x")


class _FakeResp:
    def __init__(self, content=b"ID3fakeaudio", status_code=200, text=""):
        self.content = content
        self.status_code = status_code
        self.text = text


def test_openai_posts_speech_and_writes_mp3(tmp_path):
    posts = []

    def http_post(url, headers, json):
        posts.append((url, headers, json))
        return _FakeResp()

    run = _RunRecorder(duration="4.20")
    p = OpenAITTSProvider(base_url="https://relay.example", api_key="sk-x",
                          model="tts-1", voice="alloy", output_dir=str(tmp_path),
                          http_post=http_post, run=run)
    res = p.synthesize(text="crypto markets moved")
    assert p.name == "openai"
    assert res.fmt == "mp3" and res.audio_path.endswith(".mp3")
    assert res.duration_seconds == 4.2
    url, headers, body = posts[0]
    assert url == "https://relay.example/v1/audio/speech"
    assert headers["Authorization"] == "Bearer sk-x"
    assert body["model"] == "tts-1" and body["voice"] == "alloy"
    assert body["input"] == "crypto markets moved" and body["response_format"] == "mp3"


def test_openai_raises_on_http_error(tmp_path):
    def http_post(url, headers, json):
        return _FakeResp(status_code=503, text="model_not_found")
    with pytest.raises(RuntimeError, match="HTTP 503"):
        OpenAITTSProvider(base_url="https://r", api_key="k", model="tts-1",
                          output_dir=str(tmp_path), http_post=http_post).synthesize(text="x")
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts_providers.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.tts.say'`.

- [ ] **Step 3: Create `backend/app/video/tts/say.py`:**

```python
from __future__ import annotations

import hashlib
import os
import subprocess

from app.video.ffmpeg_util import ffprobe_duration
from app.video.tts.base import TTSResult


def _default_run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout, p.stderr


class SayTTSProvider:
    """Zero-key TTS via macOS `say`. Real (if robotic) English voiceover; the default
    when no OpenAI-compatible TTS model is configured. Text is passed via `-f <file>`
    to avoid CLI escaping/length limits on long scripts."""

    name = "say"

    def __init__(self, *, output_dir="./data/videos", run=None, voice=None):
        self._output_dir = os.path.abspath(output_dir)
        self._run = run or _default_run
        self._voice = voice

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult:
        os.makedirs(self._output_dir, exist_ok=True)
        digest = hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]
        txt_path = os.path.join(self._output_dir, f"tts_say_{digest}.txt")
        aiff_path = os.path.join(self._output_dir, f"tts_say_{digest}.aiff")
        wav_path = os.path.join(self._output_dir, f"tts_say_{digest}.wav")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text or "")
        say_cmd = ["say", "-f", txt_path, "-o", aiff_path]
        v = voice or self._voice
        if v:
            say_cmd[1:1] = ["-v", v]
        rc, out, err = self._run(say_cmd)
        if rc != 0:
            raise RuntimeError(f"say failed rc={rc}: {(err or out or '').strip()[:200]}")
        rc, out, err = self._run(["ffmpeg", "-y", "-i", aiff_path, wav_path])
        if rc != 0:
            raise RuntimeError(f"say ffmpeg aiff->wav failed rc={rc}: {(err or out or '').strip()[:200]}")
        duration = ffprobe_duration(wav_path, run=self._run)
        return TTSResult(audio_path=wav_path, duration_seconds=duration, fmt="wav")
```

- [ ] **Step 4: Create `backend/app/video/tts/openai.py`:**

```python
from __future__ import annotations

import hashlib
import os

from app.video.ffmpeg_util import ffprobe_duration
from app.video.tts.base import TTSResult


class OpenAITTSProvider:
    """TTS via an OpenAI-compatible `/v1/audio/speech` endpoint (e.g. the newapi relay).
    Reuses the relay key/base. Activates when a TTS model is provisioned on the relay."""

    name = "openai"

    def __init__(self, *, base_url, api_key, model="tts-1", voice="alloy",
                 output_dir="./data/videos", http_post=None, run=None):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._voice = voice
        self._output_dir = os.path.abspath(output_dir)
        self._http_post = http_post or self._default_post
        self._run = run

    def _default_post(self, url, headers, json):
        import httpx
        return httpx.post(url, headers=headers, json=json, timeout=120)

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult:
        os.makedirs(self._output_dir, exist_ok=True)
        url = f"{self._base}/v1/audio/speech"
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "voice": voice or self._voice,
            "input": text or "",
            "response_format": "mp3",
        }
        resp = self._http_post(url, headers=headers, json=payload)
        status = getattr(resp, "status_code", 200)
        if status >= 400:
            body = getattr(resp, "text", "") or ""
            raise RuntimeError(f"tts /v1/audio/speech HTTP {status}: {body[:200]}")
        digest = hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]
        path = os.path.join(self._output_dir, f"tts_openai_{digest}.mp3")
        with open(path, "wb") as f:
            f.write(resp.content)
        duration = ffprobe_duration(path, run=self._run)
        return TTSResult(audio_path=path, duration_seconds=duration, fmt="mp3")
```

- [ ] **Step 5: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts_providers.py -q` (4 passed).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/tts/say.py backend/app/video/tts/openai.py backend/tests/test_tts_providers.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): SayTTSProvider (macOS say) + OpenAITTSProvider (relay /v1/audio/speech)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: resolve_tts_provider factory

**Files:**
- Create: `backend/app/video/tts/factory.py`
- Test: `backend/tests/test_tts_factory.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_tts_factory.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

from app.video.tts.factory import resolve_tts_provider
from app.video.tts.fake import FakeTTSProvider


def _settings(**kw):
    base = dict(tts_provider="auto", tts_model="", tts_voice="alloy",
                tts_base_url=None, tts_api_key=None,
                anthropic_base_url="https://relay", anthropic_api_key="sk-x",
                video_output_dir="./data/videos")
    base.update(kw)
    return SimpleNamespace(**base)


def test_explicit_fake():
    p = resolve_tts_provider(_settings(tts_provider="fake"))
    assert isinstance(p, FakeTTSProvider)


def test_auto_picks_openai_when_model_and_key_present():
    from app.video.tts.openai import OpenAITTSProvider
    p = resolve_tts_provider(_settings(tts_provider="auto", tts_model="tts-1"))
    assert isinstance(p, OpenAITTSProvider)
    assert p._model == "tts-1" and p._base == "https://relay" and p._key == "sk-x"


def test_openai_uses_dedicated_base_key_over_anthropic():
    from app.video.tts.openai import OpenAITTSProvider
    p = resolve_tts_provider(_settings(tts_provider="openai", tts_model="tts-1",
                                       tts_base_url="https://tts", tts_api_key="sk-tts"))
    assert isinstance(p, OpenAITTSProvider) and p._base == "https://tts" and p._key == "sk-tts"


def test_openai_choice_without_model_falls_back_to_fake():
    p = resolve_tts_provider(_settings(tts_provider="openai", tts_model=""))
    assert isinstance(p, FakeTTSProvider)


def test_explicit_say_when_say_missing_falls_back_to_fake(monkeypatch):
    import app.video.tts.factory as fac
    monkeypatch.setattr(fac.shutil, "which", lambda name: None)
    p = resolve_tts_provider(_settings(tts_provider="say"))
    assert isinstance(p, FakeTTSProvider)
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts_factory.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.tts.factory'`.

- [ ] **Step 3: Create `backend/app/video/tts/factory.py`:**

```python
from __future__ import annotations

import logging
import shutil

logger = logging.getLogger(__name__)


def resolve_tts_provider(settings=None, *, run=None, http_post=None):
    """Return a TTS provider per settings. Order for 'auto': openai (if model+key) -> say
    (if binary present) -> fake. Explicit choices fall back to fake if unavailable.
    Never raises — a misconfigured TTS provider must not break video generation."""
    from app.video.tts.fake import FakeTTSProvider

    if settings is None:
        from app.config import settings as global_settings
        settings = global_settings

    choice = (getattr(settings, "tts_provider", "auto") or "auto").lower()
    out_dir = getattr(settings, "video_output_dir", "./data/videos")

    def _openai():
        base = getattr(settings, "tts_base_url", None) or getattr(settings, "anthropic_base_url", None)
        key = getattr(settings, "tts_api_key", None) or getattr(settings, "anthropic_api_key", None)
        model = getattr(settings, "tts_model", "") or ""
        if not (base and key and model):
            return None
        from app.video.tts.openai import OpenAITTSProvider
        return OpenAITTSProvider(
            base_url=base, api_key=key, model=model,
            voice=getattr(settings, "tts_voice", "alloy"),
            output_dir=out_dir, http_post=http_post, run=run,
        )

    def _say():
        if shutil.which("say") is None:
            return None
        from app.video.tts.say import SayTTSProvider
        return SayTTSProvider(output_dir=out_dir, run=run)  # system default voice

    try:
        if choice == "openai":
            return _openai() or FakeTTSProvider(output_dir=out_dir)
        if choice == "say":
            return _say() or FakeTTSProvider(output_dir=out_dir)
        if choice == "fake":
            return FakeTTSProvider(output_dir=out_dir)
        # auto
        return _openai() or _say() or FakeTTSProvider(output_dir=out_dir)
    except Exception as exc:  # noqa: BLE001 - never break video-gen on a misconfigured TTS
        logger.warning("tts provider init failed (%s: %s); falling back to fake",
                       exc.__class__.__name__, exc)
        return FakeTTSProvider(output_dir=out_dir)
```

- [ ] **Step 4: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_tts_factory.py -q` (5 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/tts/factory.py backend/tests/test_tts_factory.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): resolve_tts_provider factory (auto: openai->say->fake)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: FacelessVideoProvider + real ffmpeg end-to-end test

**Files:**
- Create: `backend/app/video/faceless.py`
- Test: `backend/tests/test_faceless_video.py`

- [ ] **Step 1: Write the failing test** — create `backend/tests/test_faceless_video.py`:

```python
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from app.video.faceless import FacelessVideoProvider
from app.video.fake import FakeVideoProvider
from app.video.tts.fake import FakeTTSProvider

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _stream_types(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "default=nw=1:np=1", path],
        capture_output=True, text=True,
    )
    return p.stdout


def _duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:np=1", path],
        capture_output=True, text=True,
    )
    return float(p.stdout.strip())


def test_narration_strips_heading_lines(tmp_path):
    prov = FacelessVideoProvider(tts=FakeTTSProvider(output_dir=str(tmp_path)),
                                 visual=FakeVideoProvider(), output_dir=str(tmp_path))
    assert prov._narration("# Title\n\nHook line.\nSecond line.") == "Hook line. Second line."


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe required for real compose")
def test_faceless_composes_real_playable_mp4(tmp_path):
    tts = FakeTTSProvider(output_dir=str(tmp_path))
    prov = FacelessVideoProvider(
        tts=tts, visual=FakeVideoProvider(),
        output_dir=str(tmp_path), public_base_url="http://127.0.0.1:8010",
    )
    script = "Bitcoin broke out today. Here is why it matters. Watch the liquidity move."
    res = prov.generate(script=script, brief=None, params={})

    assert res.provider == "faceless"
    assert res.metadata["visual_provider"] == "fake"
    assert res.metadata["caption_chunks"] >= 3
    fname = res.media_url.rsplit("/", 1)[-1]
    path = os.path.join(str(tmp_path), fname)
    assert os.path.exists(path)
    streams = _stream_types(path)
    assert "video" in streams and "audio" in streams
    # duration tracks the TTS voiceover length (11 words / 2.7 ~= 4.07s)
    assert abs(_duration(path) - res.duration) < 1.0
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_faceless_video.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.faceless'`.

- [ ] **Step 3: Create `backend/app/video/faceless.py`:**

```python
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile

from app.video.base import VideoResult
from app.video.captions import build_ass, chunk_caption

logger = logging.getLogger(__name__)


class FacelessVideoProvider:
    """Compose a faceless 口播 vertical video: TTS voiceover + an inner clip provider's
    b-roll background + burned ASS captions, stitched by ffmpeg. Implements the
    VideoProvider protocol so the governor/guardrails/factory reuse it unchanged.

    NOTE: generate() is synchronous and blocks up to proc_timeout on ffmpeg. Async job
    model is a follow-up before high-concurrency use.
    """

    name = "faceless"

    def __init__(self, *, tts, visual, output_dir="./data/videos",
                 public_base_url="http://127.0.0.1:8010", run=None,
                 resolution=(1080, 1920), proc_timeout=600):
        self._tts = tts
        self._visual = visual
        self._output_dir = os.path.abspath(output_dir)
        self._public_base = public_base_url.rstrip("/")
        self._run = run or self._default_run
        self._w, self._h = resolution
        self._proc_timeout = proc_timeout

    def _default_run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=self._proc_timeout)
        return p.returncode, p.stdout, p.stderr

    def _narration(self, script: str) -> str:
        lines = []
        for ln in (script or "").splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)
        return " ".join(lines).strip() or (script or "").strip()

    def _gradient_bg(self, duration: float, tmp: str) -> str:
        out = os.path.join(tmp, "bg.mp4")
        rc, o, e = self._run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"gradients=s={self._w}x{self._h}:d={duration}:speed=0.02:c0=0x1A0B2E:c1=0x8B5CFF",
            "-t", str(duration), "-pix_fmt", "yuv420p", out,
        ])
        if rc != 0:
            raise RuntimeError(f"faceless gradient bg failed rc={rc}: {(e or o or '').strip()[:200]}")
        return out

    def _download(self, url: str, tmp: str) -> str:
        import urllib.request
        out = os.path.join(tmp, "bg_src.mp4")
        try:
            urllib.request.urlretrieve(url, out)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"faceless: failed to download background clip {url}: {exc}") from exc
        return out

    def _background(self, clip, duration: float, tmp: str) -> str:
        if getattr(clip, "provider", "") == "fake":
            return self._gradient_bg(duration, tmp)
        url = clip.media_url
        if url.startswith("http://") or url.startswith("https://"):
            return self._download(url, tmp)
        fname = url.rsplit("/", 1)[-1]
        local = os.path.join(self._output_dir, fname)
        if os.path.exists(local):
            return local
        raise RuntimeError(f"faceless: background clip not found locally: {url}")

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        narration = self._narration(script)
        tts_result = self._tts.synthesize(text=narration, voice=params.get("voice"))
        duration = round(float(tts_result.duration_seconds), 2)
        os.makedirs(self._output_dir, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="faceless_")
        try:
            clip = self._visual.generate(script=script, brief=brief, params=params)
            bg = self._background(clip, duration, tmp)
            chunks = chunk_caption(narration)
            ass_path = os.path.join(tmp, "captions.ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(build_ass(chunks, duration, resolution=(self._w, self._h)))
            digest = hashlib.sha1(narration.encode("utf-8")).hexdigest()[:16]
            fname = f"faceless_{digest}.mp4"
            out_path = os.path.join(self._output_dir, fname)
            vf = (f"scale={self._w}:{self._h}:force_original_aspect_ratio=increase,"
                  f"crop={self._w}:{self._h},ass={ass_path}")
            rc, o, e = self._run([
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", bg, "-i", tts_result.audio_path,
                "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-t", str(duration),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path,
            ])
            if rc != 0:
                raise RuntimeError(f"faceless ffmpeg compose failed rc={rc}: {(e or o or '').strip()[:300]}")
            return VideoResult(
                media_url=f"{self._public_base}/media/{fname}",
                duration=duration,
                cost=float(getattr(clip, "cost", 0.0) or 0.0),
                provider=self.name,
                dedup_key=digest,
                metadata={
                    "tts_provider": getattr(self._tts, "name", ""),
                    "visual_provider": getattr(clip, "provider", ""),
                    "caption_chunks": len(chunks),
                },
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 4: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_faceless_video.py -q` (2 passed; the compose test runs for real since ffmpeg is present). If the `gradients` lavfi source is unavailable on some host, the skip-guarded test still requires it — this machine has ffmpeg 8.1.1 where `gradients` exists (since ffmpeg 5.0), so it must pass here.

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/faceless.py backend/tests/test_faceless_video.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): FacelessVideoProvider composes TTS + b-roll + captions via ffmpeg\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: Wire the factory — `faceless` provider + inner clip resolution

**Files:**
- Modify: `backend/app/video/factory.py`
- Test: `backend/tests/test_video_factory.py` (extend)

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_video_factory.py`:

```python
def test_factory_returns_faceless_when_configured(monkeypatch, tmp_path):
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.faceless import FacelessVideoProvider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "faceless", raising=False)
    monkeypatch.setattr(settings, "faceless_visual", "fake", raising=False)
    monkeypatch.setattr(settings, "tts_provider", "fake", raising=False)
    monkeypatch.setattr(settings, "video_output_dir", str(tmp_path), raising=False)
    p = resolve_video_provider()
    assert isinstance(p, FacelessVideoProvider)
    assert p.name == "faceless"
    # inner visual is a plain clip provider, never another faceless (no recursion)
    assert isinstance(p._visual, FakeVideoProvider)


def test_faceless_inner_visual_never_faceless(monkeypatch, tmp_path):
    """faceless_visual must resolve to a clip provider, even if set to 'faceless'."""
    from app.config import settings
    from app.video.factory import resolve_video_provider
    from app.video.faceless import FacelessVideoProvider
    from app.video.fake import FakeVideoProvider

    monkeypatch.setattr(settings, "video_provider", "faceless", raising=False)
    monkeypatch.setattr(settings, "faceless_visual", "faceless", raising=False)  # nonsense on purpose
    monkeypatch.setattr(settings, "tts_provider", "fake", raising=False)
    monkeypatch.setattr(settings, "video_output_dir", str(tmp_path), raising=False)
    p = resolve_video_provider()
    assert isinstance(p, FacelessVideoProvider)
    assert isinstance(p._visual, FakeVideoProvider)  # fell through to fake, no recursion
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && ./.venv/bin/python -m pytest tests/test_video_factory.py -q`
  Expected: the two new tests FAIL (faceless not wired; `resolve_video_provider` returns fake).

- [ ] **Step 3: Rewrite `backend/app/video/factory.py`** to extract a clip-provider helper and add the faceless branch:

```python
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _resolve_clip_provider(settings, name):
    """Resolve a *clip* provider (aitoearn|seedance|fake) for direct use or as the
    faceless b-roll. Never returns a FacelessVideoProvider — prevents recursion."""
    from app.video.fake import FakeVideoProvider

    if name == "aitoearn" and settings.aitoearn_ai_base_url and settings.aitoearn_api_key:
        from app.connectors.aitoearn_client import AiToEarnClient
        from app.video.aitoearn import AiToEarnVideoProvider
        client = AiToEarnClient(settings.aitoearn_base_url or "", settings.aitoearn_api_key,
                                ai_base_url=settings.aitoearn_ai_base_url)
        return AiToEarnVideoProvider(client, model=settings.aitoearn_video_model)
    if name == "seedance":
        from app.video.seedance import SeedanceVideoProvider
        return SeedanceVideoProvider(
            binary=settings.dreamina_bin,
            model=settings.seedance_model,
            output_dir=settings.video_output_dir,
            public_base_url=settings.public_base_url,
        )
    return FakeVideoProvider()


def resolve_video_provider():
    """Return the configured video provider. Defaults to FakeVideoProvider. Never raises —
    a misconfigured provider must not take down the loop; it falls back to fake."""
    from app.config import settings
    from app.video.fake import FakeVideoProvider

    try:
        if settings.video_provider == "faceless":
            from app.video.faceless import FacelessVideoProvider
            from app.video.tts.factory import resolve_tts_provider
            tts = resolve_tts_provider(settings)
            visual = _resolve_clip_provider(settings, settings.faceless_visual)
            return FacelessVideoProvider(
                tts=tts, visual=visual,
                output_dir=settings.video_output_dir,
                public_base_url=settings.public_base_url,
            )
        if settings.video_provider in ("aitoearn", "seedance"):
            return _resolve_clip_provider(settings, settings.video_provider)
    except Exception as exc:  # noqa: BLE001 - never break the loop on a misconfigured provider
        logger.warning("video provider init failed (%s: %s); falling back to fake",
                       exc.__class__.__name__, exc)

    return FakeVideoProvider()
```

Note: `_resolve_clip_provider(settings, "faceless")` hits neither the aitoearn nor seedance branch → returns `FakeVideoProvider()`, satisfying the no-recursion test.

- [ ] **Step 4: Run — expect PASS.** `cd backend && ./.venv/bin/python -m pytest tests/test_video_factory.py -q` (all pass, including the 4 pre-existing tests — the aitoearn/seedance/fake/broken-fallback behavior is preserved by `_resolve_clip_provider` + the try/except).

- [ ] **Step 5: Full suite** — `cd backend && ./.venv/bin/python -m pytest -q`. Expected: **291 passed** (273 baseline + 3 tts + 5 captions + 4 tts_providers + 5 tts_factory + 2 faceless + 2 factory − overlaps; exact count may vary slightly, all green).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/video/factory.py backend/tests/test_video_factory.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(video): wire faceless provider into factory + inner clip resolution (no recursion)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Run the full backend suite once more (`cd backend && ./.venv/bin/python -m pytest -q`) — all green.
- Dispatch the final whole-implementation code review.
- Update `docs/DELIVERY.md`: video provider options are now `fake | seedance | aitoearn | faceless`; **`faceless` is the 口播 form** (AI clip b-roll + TTS voiceover + burned captions). To enable: `MATRIXLOOP_VIDEO_PROVIDER=faceless`, `MATRIXLOOP_FACELESS_VISUAL=aitoearn|seedance|fake`, `MATRIXLOOP_TTS_PROVIDER=auto` (defaults to macOS `say`, zero key). Real voiceover via relay: provision a TTS model on the relay, then set `MATRIXLOOP_TTS_MODEL=<model>` (reuses the anthropic key/base) — or `MATRIXLOOP_TTS_BASE_URL`/`MATRIXLOOP_TTS_API_KEY` for a dedicated TTS endpoint.
- `superpowers:finishing-a-development-branch` → merge to `main` (`--no-ff`).

## Non-goals (YAGNI)

- No word-level karaoke captions (char-proportional chunk timing is enough; word timestamps are a later enhancement when a TTS with timing is wired).
- No async submit/poll job model (synchronous + governor, matching seedance).
- No per-account voice mapping through `assign_voice` yet (say voices ≠ openai voices; wiring arbitrary voice names into `say -v` would break — deferred as a follow-up).
- No digital-human/avatar form (separate 形态, out of scope here).

## Self-Review

- **Spec coverage:** TTSProvider seam (T1 base+fake, T3 say+openai, T4 factory); captions (T2); FacelessVideoProvider compose (T5); config (T1); factory wiring + no-recursion (T6); headline zero-key real-ffmpeg E2E test (T5). All spec sections mapped.
- **Placeholder scan:** none — every step has full code + exact commands.
- **Type consistency:** `TTSResult(audio_path, duration_seconds, fmt)` used identically across fake/say/openai/tests; `VideoResult(media_url, duration, cost, provider, dedup_key, metadata)` matches `app/video/base.py` exactly (no `status`); `resolve_tts_provider(settings, *, run, http_post)` and `_resolve_clip_provider(settings, name)` signatures consistent between definition and callers; `ffprobe_duration(path, run=None)` consistent across say/openai.
