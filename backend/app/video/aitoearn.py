from __future__ import annotations

import logging

from app.video.base import VideoResult

logger = logging.getLogger(__name__)


class AiToEarnVideoProvider:
    """Reuse AiToEarn's video-generation pipeline over HTTP (multi-provider: Volcengine/Seedance,
    Sora, Grok, DashScope — server-side keys). Submits an async task, polls to completion, returns
    the hosted video URL. Injectable client/sleep for tests.

    NOTE: generate() is synchronous and blocks up to poll_attempts*poll_interval seconds; a fully
    async job model is a follow-up (same constraint as the other providers)."""

    name = "aitoearn"

    def __init__(self, client, *, model="seedance-1-pro", poll_attempts=40, poll_interval=5, sleep=None):
        self.client = client
        self.model = model
        self._poll_attempts = poll_attempts
        self._poll_interval = poll_interval
        import time
        self._sleep = sleep or time.sleep

    def _build_prompt(self, script, brief, params):
        if params and params.get("visual_prompt"):
            return params["visual_prompt"]
        niches = "、".join(getattr(brief, "sub_niches", None) or []) if brief else ""
        direction = getattr(brief, "main_direction", "") if brief else ""
        head = (script or "").strip().replace("\n", " ")[:200]
        bits = [b for b in [direction, niches] if b]
        style = ("Short-form vertical (9:16) b-roll for a "
                 + (", ".join(bits) if bits else "content") + " video. ")
        return style + ("Scene: " + head if head else "cinematic, dynamic, on-brand")

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        payload = {
            "model": self.model,
            "prompt": self._build_prompt(script, brief, params),
            "ratio": params.get("ratio", "9:16"),
            "duration": params.get("duration", 5),
        }
        resp = self.client.submit_video(payload) or {}
        data = resp.get("data") or {}
        task_id = data.get("id")
        if not task_id:
            raise RuntimeError(f"aitoearn video submit failed: {resp.get('message') or resp}")
        result = self._poll(task_id)
        video_url = result.get("videoUrl")
        if not video_url:
            raise RuntimeError(f"aitoearn video succeeded but no videoUrl (task {task_id})")
        return VideoResult(
            media_url=video_url,
            duration=float(payload["duration"]) if payload.get("duration") else 5.0,
            cost=float(result.get("cost") or 1.0),
            provider=self.name,
            dedup_key=str(task_id),
            metadata={"task_id": task_id, "model": self.model, "cover_url": result.get("coverUrl")},
        )

    def _poll(self, task_id: str) -> dict:
        for attempt in range(self._poll_attempts):
            resp = self.client.video_task(task_id) or {}
            data = resp.get("data") or {}
            status = data.get("status")
            logger.debug("aitoearn video poll %d/%d task=%s status=%s",
                         attempt + 1, self._poll_attempts, task_id, status)
            if status == "success":
                return data
            if status == "failure":
                err = (data.get("error") or {}).get("message") or "unknown"
                raise RuntimeError(f"aitoearn video generation failed: {err}")
            if attempt < self._poll_attempts - 1:
                self._sleep(self._poll_interval)
        raise RuntimeError(f"aitoearn video generation timed out for task {task_id}")
