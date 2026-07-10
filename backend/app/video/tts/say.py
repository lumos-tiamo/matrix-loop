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
