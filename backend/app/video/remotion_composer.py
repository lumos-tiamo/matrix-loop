from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

# per-channel palette keyed by the brief's main_direction (falls back to the AI/科普 look)
_PALETTE: list[tuple[tuple[str, ...], str, str]] = [
    (("airdrop", "空投", "撸毛", "farm"), "#8B5CFF", "#C6FF3A"),
    (("trad", "charts", "chart", "技术", "交易", "ta"), "#12233F", "#38BDF8"),
    (("yield", "defi", "gold", "黄金", "理财", "收益", "rwa"), "#3A2A08", "#F5B301"),
]


def _brand_for(brief) -> dict:
    md = (getattr(brief, "main_direction", "") or "").lower()
    color, accent = "#14331F", "#C6FF3A"  # default: AI/科普
    for keys, c, a in _PALETTE:
        if any(k in md for k in keys):
            color, accent = c, a
            break
    name = getattr(brief, "persona", None) or getattr(brief, "main_direction", None) or "Channel"
    return {
        "name": str(name)[:32],
        "color": color,
        "accent": accent,
        "handle": str(getattr(brief, "handle", "") or ""),
    }


class RemotionComposer:
    """Compose a finished vertical video with Remotion instead of ffmpeg: it stages the b-roll
    (video/image) + TTS audio into remotion/public and renders the `BrandVideo` composition
    (per-channel brand template + animated captions) headlessly via `node render.mjs`.

    Drop-in for FacelessVideoProvider's final mux: same inputs (background, audio, caption
    timings, brief), returns a finished mp4 path in `output_dir`."""

    name = "remotion"

    def __init__(self, *, remotion_dir: str, node_bin: str = "node",
                 fps: int = 30, proc_timeout: int = 900, run=None):
        self.remotion_dir = os.path.abspath(remotion_dir)
        self.node_bin = node_bin
        self.fps = fps
        self.proc_timeout = proc_timeout
        self._run = run or self._default_run

    def _default_run(self, cmd, cwd):
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=self.proc_timeout)
        return p.returncode, p.stdout, p.stderr

    def _stage(self, job_dir: str, name: str, src: str) -> str:
        """Copy/download `src` into remotion/public/jobs/<job>/<name>; return the public-relative path."""
        dst = os.path.join(job_dir, name)
        if src.startswith("http://") or src.startswith("https://"):
            import urllib.request
            urllib.request.urlretrieve(src, dst)
        else:
            if not os.path.exists(src):
                raise RuntimeError(f"remotion: source not found: {src}")
            shutil.copy(src, dst)
        rel = os.path.relpath(dst, os.path.join(self.remotion_dir, "public"))
        return rel.replace(os.sep, "/")

    def compose(self, *, background_kind: str, background_src: str, audio_path: str | None,
                duration: float, captions, brief, output_dir: str,
                resolution: tuple[int, int]) -> str:
        w, h = resolution
        digest = hashlib.sha1(
            f"{background_src}|{audio_path}|{duration}|{len(captions)}".encode("utf-8")
        ).hexdigest()[:16]
        public = os.path.join(self.remotion_dir, "public")
        job_dir = os.path.join(public, "jobs", digest)
        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(os.path.abspath(output_dir), exist_ok=True)

        try:
            bg = {"kind": "none", "src": ""}
            if background_kind == "video" and background_src:
                bg = {"kind": "video", "src": self._stage(job_dir, "bg.mp4", background_src)}
            elif background_kind == "image" and background_src:
                ext = ".png" if background_src.lower().endswith(".png") else ".jpg"
                bg = {"kind": "image", "src": self._stage(job_dir, f"bg{ext}", background_src)}

            audio_rel = self._stage(job_dir, "voice.mp3", audio_path) if audio_path else None

            props = {
                "width": w, "height": h, "fps": self.fps,
                "durationInSeconds": round(float(duration), 2),
                "background": bg,
                "audioSrc": audio_rel,
                "captions": [{"text": t, "start": round(s, 3), "end": round(e, 3)} for (t, s, e) in captions],
                "brand": _brand_for(brief),
                "title": None,
            }
            props_path = os.path.join(job_dir, "props.json")
            with open(props_path, "w") as fh:
                json.dump(props, fh, ensure_ascii=False)

            fname = f"remotion_{digest}.mp4"
            out_path = os.path.join(os.path.abspath(output_dir), fname)
            rc, out, err = self._run([self.node_bin, "render.mjs", props_path, out_path], self.remotion_dir)
            if rc != 0 or not os.path.exists(out_path):
                raise RuntimeError(f"remotion render failed rc={rc}: {(err or out or '').strip()[-400:]}")
            return out_path
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
