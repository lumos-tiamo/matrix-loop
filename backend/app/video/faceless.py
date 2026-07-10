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
            scale_crop = (f"scale={self._w}:{self._h}:force_original_aspect_ratio=increase,"
                          f"crop={self._w}:{self._h}")
            # Quote the ASS path so ffmpeg's filtergraph parser does not treat '.'/'/' as
            # option/graph separators.
            ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            vf_with_captions = f"{scale_crop},ass=filename='{ass_escaped}'"

            def _compose(vf):
                return self._run([
                    "ffmpeg", "-y", "-stream_loop", "-1", "-i", bg, "-i", tts_result.audio_path,
                    "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-t", str(duration),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path,
                ])

            rc, o, e = _compose(vf_with_captions)
            if rc != 0:
                # Some ffmpeg builds ship without libass (no `ass`/`subtitles` filter). Rather
                # than fail the whole video, degrade gracefully to no burned captions — the
                # voiceover + b-roll still produce a playable clip.
                err_txt = (e or o or "")
                if "No such filter" in err_txt or "ass" in err_txt.lower():
                    logger.warning("faceless: burned-caption filter unavailable (%s); composing "
                                   "without burned captions", err_txt.strip()[:120])
                    rc, o, e = _compose(scale_crop)
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
