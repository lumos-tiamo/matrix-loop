from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile

from app.video.base import VideoResult

logger = logging.getLogger(__name__)

# account handle -> brand prefix (drives voice, brand palette, Aurea host)
_HANDLE_BRAND = {
    "askaurea": "AU",
    "airdropedge": "AE",
    "clearchartshq": "CC",
    "quiet.yield": "QY",
    "quietyield": "QY",
}


def _brand_for(handle: str | None, brief) -> str:
    h = (handle or "").lstrip("@").lower()
    if h in _HANDLE_BRAND:
        return _HANDLE_BRAND[h]
    # infer from brief: 繁中/zh -> Aurea; else keyword on the channel direction
    lang = (getattr(brief, "language", "") or "").lower()
    if lang.startswith(("繁", "zh")):
        return "AU"
    direction = (getattr(brief, "main_direction", "") or "").lower()
    if any(k in direction for k in ("airdrop", "空投")):
        return "AE"
    if any(k in direction for k in ("chart", "trading", "行情", "图表")):
        return "CC"
    if any(k in direction for k in ("yield", "收益", "stable")):
        return "QY"
    return "AE"


def _ffdur(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip() or 0)
    except Exception:
        return 0.0


class HyperframesVideoProvider:
    """Deterministic HTML->MP4 provider (HeyGen HyperFrames). Renders the SAME watchable pipeline
    the curated matrix batch uses, from an arbitrary adopted script — so the frontend 'generate
    video' button and autopilot both yield publish-quality, low-AI-feel vertical videos.

    Shells out to hyperframes-batch/produce2.py --from-script (isolates the batch venv + npx
    hyperframes + edge-tts). Determinism (no gacha) and the pre-flight quality gate live in the
    batch pipeline; a render failure/blocker returns a failed result (never breaks the loop)."""

    name = "hyperframes"

    def __init__(self, *, batch_dir: str, python_bin: str, output_dir: str,
                 public_base_url: str, quality: str = "draft", timeout: int = 600):
        self.batch_dir = batch_dir
        self.python_bin = python_bin
        self.output_dir = os.path.abspath(output_dir)
        self.public_base_url = public_base_url.rstrip("/")
        self.quality = quality
        self.timeout = timeout

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        on_progress = params.get("on_progress")
        brand = params.get("brand") or _brand_for(params.get("account_handle"), brief)
        lang = getattr(brief, "language", None) or ("繁中" if brand == "AU" else "en")
        if on_progress:
            on_progress("hyperframes:queued", 5)

        os.makedirs(self.output_dir, exist_ok=True)
        import hashlib
        tag = hashlib.sha1((script or "").encode("utf-8")).hexdigest()[:10]
        basename = f"hf_gen_{brand}_{tag}.mp4"
        out = os.path.join(self.output_dir, basename)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as sf:
            sf.write(script or "")
            script_file = sf.name

        cmd = [
            self.python_bin, "produce2.py", "--from-script",
            "--brand", brand, "--lang", str(lang),
            "--script-file", script_file, "--out", out,
            "--quality", self.quality,
        ]
        if on_progress:
            on_progress("hyperframes:render", 25)
        try:
            proc = subprocess.run(cmd, cwd=self.batch_dir, capture_output=True, text=True,
                                  timeout=self.timeout)
        finally:
            try:
                os.remove(script_file)
            except OSError:
                pass

        ok = os.path.exists(out) and "RESULT=" in proc.stdout and "FAILED" not in proc.stdout
        if not ok:
            tail = (proc.stdout or "")[-800:] + "\n" + (proc.stderr or "")[-400:]
            logger.warning("hyperframes render failed (brand=%s): %s", brand, tail)
            raise RuntimeError(f"hyperframes render failed for brand={brand}")

        dur = _ffdur(out)
        if on_progress:
            on_progress("hyperframes:done", 100)
        return VideoResult(
            media_url=f"/media/{basename}",
            duration=dur,
            cost=0.0,
            provider=self.name,
            dedup_key=f"hf-{brand}-{tag}",
            metadata={"brand": brand, "quality": self.quality, "engine": "hyperframes"},
        )
