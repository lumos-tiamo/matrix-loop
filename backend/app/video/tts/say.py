from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import wave

from app.video.ffmpeg_util import ffprobe_duration
from app.video.tts.base import TTSResult

logger = logging.getLogger(__name__)

# macOS `say -f` mishandles UTF-8 multibyte punctuation (an em-dash truncates the utterance).
# LLM scripts are full of these, so normalize to ASCII before feeding `say`.
_ASCII_MAP = {
    "—": ", ",   # — em-dash
    "–": "-",     # – en-dash
    "‑": "-",     # non-breaking hyphen
    "‘": "'", "’": "'",   # ‘ ’ smart single quotes
    "“": '"', "”": '"',   # “ ” smart double quotes
    "…": "...",  # … ellipsis
    " ": " ",     # non-breaking space
}

# Speaking-rate bounds (words/second). Real speech is ~2-3 w/s; `say` on some machines
# silently truncates arbitrary inputs, yielding a physically-impossible >~6 w/s. We treat
# output faster than this as truncated and substitute a correct-length silent track so the
# video stays full-length with correctly-timed captions (real voice when `say` cooperates).
_EXPECTED_WPS = 2.7
_TRUNCATION_WPS = 6.0
_SILENCE_RATE = 22050


def _normalize(text: str) -> str:
    for k, v in _ASCII_MAP.items():
        text = text.replace(k, v)
    return text.encode("ascii", "ignore").decode("ascii")


def _default_run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout, p.stderr


def _write_silence(path: str, seconds: float, rate: int = _SILENCE_RATE) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(max(0.1, seconds) * rate))


class SayTTSProvider:
    """Zero-key TTS via macOS `say`. Real (if robotic) English voiceover; the default when no
    OpenAI-compatible TTS model is configured. Text is normalized to ASCII (say -f truncates on
    UTF-8 punctuation) and passed via `-f <file>` (avoids CLI escaping/length limits).

    `say` is unreliable for some inputs — it silently truncates to a few words. We detect an
    implausibly-fast result and substitute a silent track of the expected length, so the video
    is always full-length with correctly-timed captions. Reliable real voice needs a provisioned
    OpenAI-compatible TTS (see OpenAITTSProvider)."""

    name = "say"

    def __init__(self, *, output_dir="./data/videos", run=None, voice=None):
        self._output_dir = os.path.abspath(output_dir)
        self._run = run or _default_run
        self._voice = voice

    def synthesize(self, *, text: str, voice: str | None = None) -> TTSResult:
        os.makedirs(self._output_dir, exist_ok=True)
        raw = text or ""
        spoken = _normalize(raw)
        words = max(1, len(spoken.split()))
        expected = max(1.0, round(words / _EXPECTED_WPS, 2))
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        txt_path = os.path.join(self._output_dir, f"tts_say_{digest}.txt")
        aiff_path = os.path.join(self._output_dir, f"tts_say_{digest}.aiff")
        wav_path = os.path.join(self._output_dir, f"tts_say_{digest}.wav")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(spoken)
        try:
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
            # Guard against `say` truncation: a real voiceover cannot exceed ~6 words/second.
            if duration > 0 and (words / duration) > _TRUNCATION_WPS:
                logger.warning(
                    "say produced %.2fs for %d words (%.1f w/s > %.1f) — truncated; "
                    "substituting a %.2fs silent track (provision an OpenAI-compatible TTS for real voice)",
                    duration, words, words / duration, _TRUNCATION_WPS, expected,
                )
                _write_silence(wav_path, expected)
                duration = expected
            return TTSResult(audio_path=wav_path, duration_seconds=duration, fmt="wav")
        finally:
            for p in (txt_path, aiff_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
