from __future__ import annotations

import hashlib
import logging
import os

from app.video.ffmpeg_util import ffprobe_duration
from app.video.tts.base import TTSResult

logger = logging.getLogger(__name__)

# Free, no-key neural TTS via Microsoft Edge. Traditional-Chinese (Taiwan) voices for
# the Aurea 繁中 channel; English voices available for the SEA-English accounts.
DEFAULT_VOICE = "zh-TW-HsiaoChenNeural"   # 曉臻 — natural zh-TW female
VOICES = {
    "zh-TW-f": "zh-TW-HsiaoChenNeural",
    "zh-TW-m": "zh-TW-YunJheNeural",
    "en-f": "en-US-AvaNeural",
    "en-m": "en-US-AndrewNeural",
}


def _valid_voice(voice: str | None) -> str:
    """Resolve to a real edge-tts voice. Accepts our aliases, passes through full
    Neural names, and falls back to the zh-TW default for anything unrecognized
    (e.g. an OpenAI voice like 'alloy' left in tts_voice) — never crash on config."""
    if not voice:
        return DEFAULT_VOICE
    if voice in VOICES:
        return VOICES[voice]
    if voice.endswith("Neural") and "-" in voice:  # looks like a real edge voice id
        return voice
    logger.warning("edge TTS: unrecognized voice %r; using default %s", voice, DEFAULT_VOICE)
    return DEFAULT_VOICE


def _synthesize_mp3(text: str, voice: str, out_path: str, rate: str, volume: str) -> None:
    """Blocking edge-tts synth to an mp3 file. Isolated so tests can inject a fake."""
    import asyncio

    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await communicate.save(out_path)

    asyncio.run(_run())


class EdgeTTSProvider:
    """Neural TTS via edge-tts (free, no API key). Default voice is zh-TW for Aurea.

    `synth` is injectable (defaults to the real edge-tts call) so tests never hit the
    network. Mirrors the SayTTSProvider shape: writes an mp3, probes real duration.
    """

    name = "edge"

    def __init__(
        self,
        *,
        output_dir="./data/videos",
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        volume: str = "+0%",
        synth=None,
        run=None,
    ):
        self._output_dir = os.path.abspath(output_dir)
        self._voice = _valid_voice(voice)
        self._rate = rate
        self._volume = volume
        self._synth = synth or _synthesize_mp3
        self._run = run

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult:
        os.makedirs(self._output_dir, exist_ok=True)
        raw = (text or "").strip()
        if not raw:
            raise ValueError("edge TTS: empty text")
        v = _valid_voice(voice) if voice else self._voice
        digest = hashlib.sha1(f"{v}:{raw}".encode("utf-8")).hexdigest()[:16]
        mp3_path = os.path.join(self._output_dir, f"tts_edge_{digest}.mp3")

        self._synth(raw, v, mp3_path, self._rate, self._volume)
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            raise RuntimeError(f"edge TTS produced no audio (voice={v!r})")

        duration = ffprobe_duration(mp3_path, run=self._run)
        return TTSResult(audio_path=mp3_path, duration_seconds=round(duration, 2), fmt="mp3")
