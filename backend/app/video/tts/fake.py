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
