from __future__ import annotations

import logging
import time

from app.image.base import ImageResult

logger = logging.getLogger(__name__)

TERMINAL = {"succeeded", "failed", "canceled"}


class CanvasImageProvider:
    """Image generation via the Infinite-Canvas-GT headless job API (a same-machine
    aggregator fronting modelscope/jimeng/volcengine/openai/gemini). Runs in its own
    venv, so we talk to it over loopback HTTP — never in-process.

    Contract (see infinite-canvas-gt/docs/JOB-API.md):
      POST /api/jobs {jobs:[{type,prompt,provider?,input_image?,params?}]} -> {jobs:[{job_id}]}
      GET  /api/jobs/{id} -> {status, artifacts:[{kind,path,url,meta}]}

    Artifacts carry a same-machine absolute ``path`` we hand straight to faceless.
    http_* are injectable so tests never hit the network (repo convention)."""

    name = "canvas"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:3000",
        app_token: str = "",
        model_provider: str = "modelscope",
        output_dir: str = "./data/videos",
        public_base_url: str = "http://127.0.0.1:8010",
        http_post=None,
        http_get=None,
        poll_interval: float = 2.0,
        max_wait: float = 600.0,
        sleep=time.sleep,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.app_token = app_token
        self.model_provider = model_provider
        self.output_dir = output_dir
        self.public_base_url = (public_base_url or "").rstrip("/")
        self._http_post = http_post or self._default_post
        self._http_get = http_get or self._default_get
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self._sleep = sleep

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.app_token:
            h["X-App-Token"] = self.app_token
        return h

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx

        resp = httpx.post(url, headers=headers, json=json, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def generate(
        self, *, prompt: str, refs: list[str] | None = None, params: dict | None = None
    ) -> ImageResult:
        params = params or {}
        job: dict = {
            "type": "image_to_image" if refs else "text_to_image",
            "prompt": prompt,
            "provider": params.get("provider") or self.model_provider,
        }
        if refs:
            job["input_image"] = refs[0]  # same-machine path or url; character-lock ref
        # pass through model/size/etc. (drop our own control keys)
        passthrough = {k: v for k, v in params.items()
                       if k not in ("provider", "filename", "model_provider")}
        if passthrough:
            job["params"] = passthrough

        submitted = self._http_post(f"{self.base_url}/api/jobs", self._headers(), {"jobs": [job]})
        jobs = submitted.get("jobs") or []
        if not jobs or not jobs[0].get("job_id"):
            raise RuntimeError(f"canvas: submit returned no job_id: {str(submitted)[:200]}")
        job_id = jobs[0]["job_id"]

        waited = 0.0
        rec: dict = {}
        while True:
            rec = self._http_get(f"{self.base_url}/api/jobs/{job_id}", self._headers())
            status = (rec.get("status") or "").lower()
            if status in TERMINAL:
                break
            if waited >= self.max_wait:
                raise TimeoutError(f"canvas job {job_id} not done after {self.max_wait}s (status={status})")
            self._sleep(self.poll_interval)
            waited += self.poll_interval

        if (rec.get("status") or "").lower() != "succeeded":
            raise RuntimeError(f"canvas job {job_id} {rec.get('status')}: {rec.get('error')}")
        arts = rec.get("artifacts") or []
        img = next((a for a in arts if (a.get("kind") or "").startswith("image") or a.get("path")), None)
        if not img or not img.get("path"):
            raise RuntimeError(f"canvas job {job_id} succeeded but no image artifact: {str(arts)[:200]}")

        path = img["path"]
        mime = (img.get("meta") or {}).get("mime") or "image/png"
        media_url = img.get("url") or (
            f"{self.public_base_url}{img['url']}" if img.get("url") else path
        )
        return ImageResult(
            path=path,
            media_url=media_url,
            mime=mime,
            provider=self.name,
            prompt=prompt,
            cost=0.0,
            metadata={"job_id": job_id, "provider": job["provider"], "artifacts": len(arts)},
        )
