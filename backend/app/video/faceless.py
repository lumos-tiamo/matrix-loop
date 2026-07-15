from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile

from app.video.base import VideoResult
from app.video.captions import chunk_caption, plan_caption_timings, render_caption_images

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
                 resolution=(1080, 1920), proc_timeout=600, compositor=None):
        self._tts = tts
        self._visual = visual
        self._output_dir = os.path.abspath(output_dir)
        self._public_base = public_base_url.rstrip("/")
        self._run = run or self._default_run
        self._w, self._h = resolution
        self._proc_timeout = proc_timeout
        # optional final-mux strategy (e.g. RemotionComposer); None = built-in ffmpeg mux
        self._compositor = compositor

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
            msg = f"faceless gradient bg failed rc={rc}: {(e or o or '').strip()[:200]}"
            logger.error(msg)
            raise RuntimeError(msg)
        return out

    def _download(self, url: str, tmp: str) -> str:
        import urllib.request
        out = os.path.join(tmp, "bg_src.mp4")
        try:
            urllib.request.urlretrieve(url, out)
        except Exception as exc:  # noqa: BLE001
            msg = f"faceless: failed to download background clip {url}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc
        return out

    def _still_bg(self, image_path: str, duration: float, tmp: str) -> str:
        """Turn a single still image (e.g. an Aurea key visual) into a full-length
        vertical background with a slow zoom (Ken Burns), so a static image becomes a
        living talking-head backdrop under the voiceover + captions."""
        out = os.path.join(tmp, "bg.mp4")
        fps = 30
        frames = max(1, int(duration * fps))
        # scale to cover, then a gentle 1.0->1.08 zoom over the clip
        vf = (
            f"scale={self._w}:{self._h}:force_original_aspect_ratio=increase,"
            f"crop={self._w}:{self._h},"
            f"zoompan=z='min(zoom+0.0006,1.08)':d={frames}:"
            f"s={self._w}x{self._h}:fps={fps}"
        )
        rc, o, e = self._run([
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p", out,
        ])
        if rc != 0:
            msg = f"faceless still bg failed rc={rc}: {(e or o or '').strip()[:200]}"
            logger.error(msg)
            raise RuntimeError(msg)
        return out

    def _background(self, clip, duration: float, tmp: str) -> str:
        if getattr(clip, "provider", "") == "fake":
            return self._gradient_bg(duration, tmp)
        if getattr(clip, "provider", "") == "still":
            path = (clip.metadata or {}).get("path") or clip.media_url
            if not os.path.exists(path):
                raise RuntimeError(f"faceless: still image not found: {path}")
            return self._still_bg(path, duration, tmp)
        url = clip.media_url
        if url.startswith("http://") or url.startswith("https://"):
            return self._download(url, tmp)
        if os.path.isabs(url) and os.path.exists(url):
            return url  # a same-machine clip (e.g. waoowaoo b-roll) — use it in place
        fname = os.path.basename(url.rsplit("/", 1)[-1])
        local = os.path.join(self._output_dir, fname)
        if os.path.exists(local):
            return local
        msg = f"faceless: background clip not found locally: {url}"
        logger.error(msg)
        raise RuntimeError(msg)

    def _raw_visual_source(self, clip):
        """Map an inner-visual clip to (kind, src) for an external compositor: fake -> gradient,
        still -> the source image, otherwise the b-roll video (local path or url)."""
        prov = getattr(clip, "provider", "")
        if prov == "fake":
            return "none", ""
        if prov == "still":
            return "image", (getattr(clip, "metadata", {}) or {}).get("path") or clip.media_url
        return "video", clip.media_url

    def _compose_external(self, clip, tts_result, narration: str, duration: float, brief) -> VideoResult:
        """Delegate the final mux to self._compositor (e.g. Remotion) instead of ffmpeg."""
        kind, src = self._raw_visual_source(clip)
        timings = plan_caption_timings(chunk_caption(narration), duration)
        out_path = self._compositor.compose(
            background_kind=kind, background_src=src or "",
            audio_path=getattr(tts_result, "audio_path", None), duration=duration,
            captions=timings, brief=brief, output_dir=self._output_dir,
            resolution=(self._w, self._h),
        )
        fname = os.path.basename(out_path)
        digest = hashlib.sha1(narration.encode("utf-8")).hexdigest()[:16]
        return VideoResult(
            media_url=f"{self._public_base}/media/{fname}",
            duration=duration,
            cost=float(getattr(clip, "cost", 0.0) or 0.0),
            provider=self.name,
            dedup_key=digest,
            metadata={"tts_provider": getattr(self._tts, "name", ""),
                      "visual_provider": getattr(clip, "provider", ""),
                      "compositor": getattr(self._compositor, "name", "external")},
        )

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        _on_progress = params.get("on_progress")

        def rep(stage: str, pct: int) -> None:
            if _on_progress:
                try: _on_progress(stage, pct)
                except Exception: pass  # noqa: BLE001 - progress must not break generation

        rep("配音生成", 5)
        narration = self._narration(script)
        tts_result = self._tts.synthesize(text=narration, voice=params.get("voice"))
        duration = round(float(tts_result.duration_seconds), 2)
        os.makedirs(self._output_dir, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="faceless_")
        try:
            clip = self._visual.generate(script=script, brief=brief, params=params)  # visual reports 10→88
            rep("字幕 + 合成", 90)
            if self._compositor is not None:
                result = self._compose_external(clip, tts_result, narration, duration, brief)
                rep("完成合成", 99)
                return result
            bg = self._background(clip, duration, tmp)
            chunks = chunk_caption(narration)
            timings = plan_caption_timings(chunks, duration)
            cap_imgs = render_caption_images(timings, resolution=(self._w, self._h), out_dir=tmp)
            digest = hashlib.sha1(narration.encode("utf-8")).hexdigest()[:16]
            fname = f"faceless_{digest}.mp4"
            out_path = os.path.join(self._output_dir, fname)

            cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg, "-i", tts_result.audio_path]
            for png, _, _ in cap_imgs:
                cmd += ["-loop", "1", "-i", png]
            fc = [f"[0:v]scale={self._w}:{self._h}:force_original_aspect_ratio=increase,"
                  f"crop={self._w}:{self._h}[v0]"]
            last = "v0"
            for idx, (_png, start, end) in enumerate(cap_imgs):
                inp = idx + 2  # inputs: 0=bg, 1=audio, 2.. = caption pngs
                nxt = f"v{idx + 1}"
                fc.append(f"[{last}][{inp}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
                last = nxt
            cmd += ["-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "1:a:0",
                    "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", out_path]
            rc, o, e = self._run(cmd)
            if rc != 0:
                msg = f"faceless ffmpeg compose failed rc={rc}: {(e or o or '').strip()[:300]}"
                logger.error(msg)
                raise RuntimeError(msg)
            rep("完成合成", 99)
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
