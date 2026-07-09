from __future__ import annotations

import json
import logging
import os
import time

from app.video.base import VideoResult

logger = logging.getLogger(__name__)


def _parse_json(text):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        # dreamina may print a plain error line (e.g. permission gate) instead of JSON
        return None


class SeedanceVideoProvider:
    name = "seedance"

    def __init__(
        self,
        *,
        bin="dreamina",
        model="seedance2.0fast",
        output_dir="./data/videos",
        public_base_url="http://127.0.0.1:8010",
        run=None,
        sleep=None,
        poll_attempts=60,
        poll_interval=5,
    ):
        self._bin = bin
        self._model = model
        self._output_dir = output_dir
        self._public_base = public_base_url.rstrip("/")
        self._run = run or self._default_run
        self._sleep = sleep or time.sleep
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval

    def _default_run(self, args):
        import subprocess

        p = subprocess.run(
            [self._bin, *args], capture_output=True, text=True, timeout=600
        )
        return p.returncode, p.stdout, p.stderr

    def _build_prompt(self, script, brief, params):
        if params and params.get("visual_prompt"):
            return params["visual_prompt"]
        niches = (
            "、".join(getattr(brief, "sub_niches", None) or []) if brief else ""
        )
        direction = getattr(brief, "main_direction", "") if brief else ""
        head = (script or "").strip().replace("\n", " ")[:200]
        bits = [b for b in [direction, niches] if b]
        style = (
            "Short-form vertical (9:16) b-roll for a "
            + (", ".join(bits) if bits else "content")
            + " video. "
        )
        return style + ("Scene: " + head if head else "cinematic, neon, dynamic")

    def generate(self, *, script, brief, params):
        prompt = self._build_prompt(script, brief, params)
        rc, out, err = self._run(
            [
                "text2video",
                f"--prompt={prompt}",
                f"--model_version={self._model}",
                "--duration=5",
                "--ratio=9:16",
                "--poll=0",
            ]
        )
        data = _parse_json(out)
        if data is None:
            raise RuntimeError(
                f"seedance submit failed: {(out or err or '').strip()[:300]}"
            )
        submit_id = data.get("submit_id")
        status = data.get("gen_status")
        if not submit_id or status == "fail":
            raise RuntimeError(
                f"seedance submit rejected: {data.get('fail_reason') or out}"
            )
        os.makedirs(self._output_dir, exist_ok=True)
        result = self._poll_download(submit_id)
        filename = self._extract_media_filename(result)
        media_url = f"{self._public_base}/media/{filename}"
        duration = result.get("duration") if isinstance(result, dict) else None
        return VideoResult(
            media_url=media_url,
            duration=float(duration) if duration else 5.0,
            cost=float((result or {}).get("credit_cost") or 1.0),
            provider=self.name,
            dedup_key=str(submit_id),
            metadata={"submit_id": submit_id},
        )

    def _poll_download(self, submit_id):
        for attempt in range(self._poll_attempts):
            rc, out, err = self._run(
                [
                    "query_result",
                    f"--submit_id={submit_id}",
                    f"--download_dir={self._output_dir}",
                ]
            )
            res = _parse_json(out)
            if res is None:
                raise RuntimeError(
                    f"seedance query failed: {(out or err or '').strip()[:300]}"
                )
            status = res.get("gen_status")
            if status == "success":
                return res
            if status == "fail":
                raise RuntimeError(
                    f"seedance generation failed: {res.get('fail_reason') or out}"
                )
            if attempt < self._poll_attempts - 1:
                self._sleep(self._poll_interval)
        raise RuntimeError(
            f"seedance generation timed out for submit_id={submit_id}"
        )

    def _extract_media_filename(self, result):
        # TODO: verify exact query_result media field against a real run (account currently tier-gated)
        if isinstance(result, dict):
            for key in (
                "download_path",
                "local_path",
                "path",
                "file_path",
                "media",
                "video_url",
                "url",
            ):
                val = result.get(key)
                if isinstance(val, str) and val:
                    return os.path.basename(val)
        # fallback: newest mp4 in output_dir
        try:
            mp4s = [
                f
                for f in os.listdir(self._output_dir)
                if f.lower().endswith(".mp4")
            ]
            if mp4s:
                mp4s.sort(
                    key=lambda f: os.path.getmtime(
                        os.path.join(self._output_dir, f)
                    ),
                    reverse=True,
                )
                return mp4s[0]
        except OSError:
            pass
        raise RuntimeError(
            "seedance succeeded but no media file was found in the download dir"
        )
