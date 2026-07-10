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
