from __future__ import annotations

import logging
import os
import time
import uuid

from app.video.base import VideoResult

logger = logging.getLogger(__name__)

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"

# Default standard-model endpoints (RunningHub API, region www.runninghub.cn).
# image-to-video is the clean automation path: one Aurea still -> a moving 9:16 clip.
I2V_ENDPOINTS = {
    "wan": "alibaba/wan-2.6/image-to-video",
    "hailuo": "minimax/hailuo-2.3-fast/image-to-video",
}


class RunningHubClient:
    """Thin client for RunningHub's *standard-model* API (not the ComfyUI-workflow
    API). Protocol, reverse-engineered from the official ComfyUI_RH_OpenAPI plugin:

      - upload : POST {base}/media/upload/binary   (multipart) -> data.download_url
      - submit : POST {base}/{endpoint}            (Bearer)    -> data.taskId
      - poll   : POST {base}/query {"taskId":...}              -> data.status + results

    http_* are injectable so tests never hit the network (mirrors AiToEarnClient).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://www.runninghub.cn",
        http_post=None,
        http_upload=None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._http_post = http_post or self._default_post
        self._http_upload = http_upload or self._default_upload

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx

        resp = httpx.post(url, headers=headers, json=json, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _default_upload(self, url: str, headers: dict, file_bytes: bytes, filename: str, mime: str) -> dict:
        import httpx

        files = {"file": (filename, file_bytes, mime)}
        resp = httpx.post(url, headers=headers, files=files, timeout=max(self.timeout, 120))
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _ok(data: dict) -> dict:
        if data.get("code") not in (0, "0", None):
            raise RuntimeError(
                f"RunningHub error code={data.get('code')} msg={data.get('msg') or data.get('errorMessage')}"
            )
        return data.get("data") or {}

    def upload(self, file_bytes: bytes, filename: str, mime: str = "image/png") -> str:
        url = f"{self.base_url}/media/upload/binary"
        data = self._http_upload(url, {"Authorization": f"Bearer {self.api_key}"}, file_bytes, filename, mime)
        d = self._ok(data)
        dl = d.get("download_url") or d.get("fileUrl") or d.get("url")
        if not dl:
            raise RuntimeError(f"RunningHub upload: no download_url in {str(data)[:200]}")
        return dl

    # Standard-model API lives under /openapi/v2/. Registry `endpoint` values are the
    # bare model path (e.g. "alibaba/wan-2.6/image-to-video"); prefix it here.
    API_PREFIX = "/openapi/v2"

    def _url(self, path: str) -> str:
        p = path.lstrip("/")
        if not p.startswith("openapi/"):
            p = f"{self.API_PREFIX.strip('/')}/{p}"
        return f"{self.base_url}/{p}"

    def submit(self, endpoint: str, payload: dict) -> str:
        url = self._url(endpoint)
        data = self._http_post(url, self._headers(), payload)
        d = self._ok(data)
        task_id = d.get("taskId") or d.get("task_id") or data.get("taskId")
        if not task_id:
            raise RuntimeError(f"RunningHub submit: no taskId in {str(data)[:200]}")
        return str(task_id)

    def poll(self, task_id: str, *, interval: float = 5.0, max_wait: float = 600.0, sleep=time.sleep) -> list[str]:
        url = self._url("query")
        waited = 0.0
        while True:
            data = self._http_post(url, self._headers(), {"taskId": task_id})
            d = self._ok(data)
            status = (d.get("status") or "").strip().upper()
            if status == STATUS_SUCCESS:
                results = d.get("results") or d.get("urls") or []
                urls = [r.get("url") if isinstance(r, dict) else r for r in results]
                urls = [u for u in urls if u]
                if not urls:
                    raise RuntimeError(f"RunningHub task {task_id} SUCCESS but no result urls")
                return urls
            if status == STATUS_FAILED:
                raise RuntimeError(f"RunningHub task {task_id} FAILED: {d.get('errorMessage') or d}")
            if waited >= max_wait:
                raise TimeoutError(
                    f"RunningHub task {task_id} not done after {max_wait}s (last status={status})"
                )
            sleep(interval)
            waited += interval


class RunningHubVideoProvider:
    """image-to-video via RunningHub standard-model API.

    generate() takes an Aurea still (params['image_url'] or params['image_path'])
    and animates it into a short 9:16 clip. Falls under the VideoProvider Protocol
    so it drops into resolve_video_provider() beside seedance/aitoearn/faceless.
    """

    name = "runninghub"

    def __init__(
        self,
        *,
        client: RunningHubClient,
        model: str = "wan",
        output_dir: str = "./data/videos",
        public_base_url: str = "http://127.0.0.1:8010",
        http_get=None,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ):
        self.client = client
        self.model = model
        self.endpoint = I2V_ENDPOINTS.get(model, model)  # allow raw endpoint override
        self.output_dir = output_dir
        self.public_base_url = (public_base_url or "").rstrip("/")
        self._http_get = http_get or self._default_get
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    def _default_get(self, url: str) -> bytes:
        import httpx

        resp = httpx.get(url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    def _build_payload(self, *, image_url: str, prompt: str, params: dict) -> dict:
        """Map to the fieldKey names from the standard-model registry."""
        if self.model == "hailuo":
            return {
                "prompt": prompt,
                "enablePromptExpansion": params.get("enable_prompt_expansion", True),
                "imageUrl": image_url,
                "duration": str(params.get("duration", "6")),
            }
        # wan-2.6 (default)
        payload = {
            "imageUrl": image_url,
            "prompt": prompt,
            "resolution": str(params.get("resolution", "1080p")),
            "duration": str(params.get("duration", "5")),
            "shotType": params.get("shot_type", "single"),
        }
        if params.get("negative_prompt"):
            payload["negativePrompt"] = params["negative_prompt"]
        return payload

    def generate(self, *, script: str, brief, params: dict) -> VideoResult:
        params = params or {}
        # resolve the input still: an already-hosted url, or a local path we upload
        image_url = params.get("image_url")
        if not image_url:
            image_path = params.get("image_path")
            if not image_path or not os.path.exists(image_path):
                raise ValueError(
                    "runninghub image-to-video needs params['image_url'] or an existing "
                    "params['image_path'] (the Aurea still to animate)"
                )
            with open(image_path, "rb") as fh:
                image_url = self.client.upload(fh.read(), os.path.basename(image_path))

        prompt = params.get("motion_prompt") or script or "subtle idle motion, talking head, natural"
        payload = self._build_payload(image_url=image_url, prompt=prompt, params=params)
        task_id = self.client.submit(self.endpoint, payload)
        urls = self.client.poll(
            task_id, interval=self.poll_interval, max_wait=self.max_wait
        )

        os.makedirs(self.output_dir, exist_ok=True)
        fname = f"rh_{uuid.uuid4().hex[:12]}.mp4"
        path = os.path.join(self.output_dir, fname)
        with open(path, "wb") as fh:
            fh.write(self._http_get(urls[0]))
        media_url = f"{self.public_base_url}/videos/{fname}" if self.public_base_url else path

        return VideoResult(
            media_url=media_url,
            duration=float(params.get("duration", 5)),
            cost=0.0,
            provider=self.name,
            dedup_key=f"rh:{task_id}",
            metadata={"task_id": task_id, "endpoint": self.endpoint, "source_image": image_url,
                      "remote_url": urls[0]},
        )
