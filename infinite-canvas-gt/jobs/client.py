"""回环 HTTP 客户端 —— 用 httpx 复用服务自身的现有端点。

adapter 不碰 main.py 内部函数：submit → poll → 取产物，全部走 127.0.0.1 的现有 API，
跟前端一模一样的调用。产物 URL 统一转成本地绝对路径回传（同机模式）。
"""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable, List, Optional

import httpx

from .config import JobsConfig
from .models import Artifact, JobSpec
from .routing import RoutePlan

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")

ProgressCb = Callable[[float], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


class JobExecutionError(Exception):
    """一次执行失败（可重试）。"""


class JobCanceled(Exception):
    """作业在执行途中被取消。"""


async def _noop_progress(_: float) -> None:
    return None


async def _never_canceled() -> bool:
    return False


class JobClient:
    def __init__(self, config: JobsConfig, http: Optional[httpx.AsyncClient] = None):
        self._cfg = config
        headers = {}
        if config.app_token:
            headers["X-App-Token"] = config.app_token
        self._http = http or httpx.AsyncClient(
            base_url=config.self_base_url, headers=headers, timeout=60.0
        )
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    # ---- 对外主入口 ----

    async def run(
        self,
        plan: RoutePlan,
        spec: JobSpec,
        progress: ProgressCb = _noop_progress,
        cancel_check: CancelCheck = _never_canceled,
    ) -> List[Artifact]:
        dispatch = {
            "image": self._run_image,
            "video": self._run_video,
            "runninghub": self._run_runninghub,
            "comfyui": self._run_comfyui,
        }
        fn = dispatch.get(plan.strategy)
        if fn is None:
            raise JobExecutionError(f"未知策略 {plan.strategy!r}")
        return await fn(plan.provider, spec, progress, cancel_check)

    # ---- 策略：图片（canvas-image-tasks，含 jimeng_pending 兜底）----

    async def _run_image(self, provider, spec, progress, cancel_check) -> List[Artifact]:
        p = spec.params or {}
        body = {
            "prompt": spec.prompt,
            "provider_id": provider,
            "model": p.get("model", ""),
            "size": p.get("size", "1024x1024"),
            "quality": p.get("quality", "auto"),
            "n": int(p.get("n", 1)),
            "reference_images": self._reference_images(spec),
        }
        r = await self._post("/api/canvas-image-tasks", body)
        task_id = r.get("task_id")
        if not task_id:
            raise JobExecutionError(f"canvas-image-tasks 未返回 task_id: {r}")
        await progress(0.3)

        async def poll():
            return await self._get(f"/api/canvas-image-tasks/{task_id}")

        data = await self._poll_until(poll, self._image_task_terminal, cancel_check, progress)
        if data["_state"] == "jimeng":
            urls = await self._poll_jimeng(data["submit_id"], "image", cancel_check, progress)
            return [self._to_artifact(u) for u in urls]
        images = ((data["payload"].get("result") or {}).get("images")) or []
        return [self._to_artifact(u) for u in images]

    @staticmethod
    def _image_task_terminal(payload: dict):
        status = payload.get("status")
        if status == "succeeded":
            return {"_state": "done", "payload": payload}
        if status == "failed":
            raise JobExecutionError(payload.get("error") or "image task failed")
        if status == "jimeng_pending" and payload.get("submit_id"):
            return {"_state": "jimeng", "submit_id": payload["submit_id"]}
        return None

    # ---- 策略：视频（canvas-video，jimeng 返回 submit_id 再轮询）----

    async def _run_video(self, provider, spec, progress, cancel_check) -> List[Artifact]:
        p = spec.params or {}
        body = {
            "prompt": spec.prompt,
            "provider_id": provider,
            "duration": int(p.get("duration", 5)),
            "aspect_ratio": p.get("aspect_ratio", "16:9"),
        }
        if p.get("model"):
            body["model"] = p["model"]
        if p.get("resolution"):
            body["resolution"] = p["resolution"]
        imgs = self._reference_images(spec, role_key="role")
        if imgs:
            body["images"] = imgs
        await progress(0.2)
        r = await self._post("/api/canvas-video", body, allow_status=(200, 202))
        videos = r.get("videos") or []
        if videos:
            return [self._to_artifact(u) for u in videos]
        submit_id = r.get("submit_id") or r.get("task_id")
        if r.get("jimeng_pending") and submit_id:
            urls = await self._poll_jimeng(submit_id, "video", cancel_check, progress)
            return [self._to_artifact(u) for u in urls]
        raise JobExecutionError(f"canvas-video 无产物也无 submit_id: {r}")

    # ---- 策略：RunningHub 工作流 ----

    async def _run_runninghub(self, provider, spec, progress, cancel_check) -> List[Artifact]:
        p = spec.params or {}
        workflow_id = p.get("workflowId") or p.get("workflow_id")
        if not workflow_id:
            raise JobExecutionError("runninghub 作业需在 params.workflowId 指定工作流")
        body = {
            "workflowId": str(workflow_id),
            "nodeInfoList": p.get("nodeInfoList", []),
            "useWallet": bool(p.get("useWallet", False)),
        }
        if p.get("workflow") is not None:
            body["workflow"] = p["workflow"]
        await progress(0.2)
        r = await self._post("/api/runninghub/workflow-submit", body)
        task_id = (r.get("data") or {}).get("taskId")
        if not task_id:
            raise JobExecutionError(f"runninghub 未返回 taskId: {r}")

        async def poll():
            return await self._get("/api/runninghub/query", params={"taskId": task_id})

        data = await self._poll_until(poll, self._runninghub_terminal, cancel_check, progress)
        urls = (data["payload"].get("data") or {}).get("urls") or []
        return [self._to_artifact(u) for u in urls]

    @staticmethod
    def _runninghub_terminal(payload: dict):
        status = str((payload.get("data") or {}).get("status") or "").upper()
        if status == "SUCCESS":
            return {"_state": "done", "payload": payload}
        if status == "FAILED":
            reason = (payload.get("data") or {}).get("failReason") or "runninghub failed"
            raise JobExecutionError(reason)
        return None

    # ---- 策略：本地 ComfyUI ----

    async def _run_comfyui(self, provider, spec, progress, cancel_check) -> List[Artifact]:
        p = spec.params or {}
        body = {
            "prompt": spec.prompt,
            "width": int(p.get("width", 1024)),
            "height": int(p.get("height", 1024)),
            "workflow_json": p.get("workflow_json", "Z-Image.json"),
            "params": p.get("node_params", {}),
            "type": p.get("type", "zimage"),
            "convert_to_jpg": bool(p.get("convert_to_jpg", False)),
        }
        await progress(0.2)
        r = await self._post("/api/canvas-comfy-tasks", body)
        task_id = r.get("task_id")
        if not task_id:
            raise JobExecutionError(f"canvas-comfy-tasks 未返回 task_id: {r}")

        async def poll():
            return await self._get(f"/api/canvas-comfy-tasks/{task_id}")

        data = await self._poll_until(poll, self._comfy_terminal, cancel_check, progress)
        images = ((data["payload"].get("result") or {}).get("images")) or []
        return [self._to_artifact(u) for u in images]

    @staticmethod
    def _comfy_terminal(payload: dict):
        status = payload.get("status")
        if status == "succeeded":
            return {"_state": "done", "payload": payload}
        if status == "failed":
            raise JobExecutionError(payload.get("error") or "comfy task failed")
        return None

    # ---- 即梦云端队列轮询 ----

    async def _poll_jimeng(self, submit_id, kind, cancel_check, progress) -> List[str]:
        async def poll():
            return await self._post(
                "/api/jimeng/query-media", {"submit_id": submit_id, "kind": kind}
            )

        def terminal(payload: dict):
            status = payload.get("status")
            if status == "succeeded":
                return {"_state": "done", "payload": payload}
            if status == "failed":
                raise JobExecutionError(payload.get("error") or "jimeng failed")
            return None

        data = await self._poll_until(poll, terminal, cancel_check, progress)
        return data["payload"].get("urls") or []

    # ---- 通用轮询循环 ----

    async def _poll_until(self, poll_fn, terminal_fn, cancel_check, progress):
        deadline = self._cfg.job_timeout
        elapsed = 0.0
        await progress(0.5)
        while elapsed < deadline:
            if await cancel_check():
                raise JobCanceled()
            payload = await poll_fn()
            result = terminal_fn(payload)
            if result is not None:
                await progress(0.95)
                return result
            await asyncio.sleep(self._cfg.poll_interval)
            elapsed += self._cfg.poll_interval
        raise JobExecutionError(f"轮询超时（{deadline:.0f}s）")

    # ---- HTTP 原语 ----

    async def _post(self, path, body, allow_status=(200,)):
        resp = await self._http.post(path, json=body)
        if resp.status_code not in allow_status and resp.status_code >= 400:
            raise JobExecutionError(f"POST {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    async def _get(self, path, params=None):
        resp = await self._http.get(path, params=params)
        if resp.status_code >= 400:
            raise JobExecutionError(f"GET {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    # ---- 辅助 ----

    def _reference_images(self, spec: JobSpec, role_key: Optional[str] = None):
        if not spec.input_image:
            return []
        ref = {"url": spec.input_image}
        # 视频的 first_frame 角色（如给了）
        if role_key and spec.params.get("frame_role"):
            ref[role_key] = spec.params["frame_role"]
        return [ref]

    def _to_artifact(self, url: str) -> Artifact:
        kind = "video" if url.lower().split("?", 1)[0].endswith(_VIDEO_EXTS) else "image"
        path = None
        clean = url.split("?", 1)[0]
        if clean.startswith("/assets/") or clean.startswith("/output/"):
            candidate = os.path.abspath(os.path.join(self._cfg.base_dir, clean.lstrip("/")))
            root = os.path.abspath(self._cfg.base_dir)
            if os.path.commonpath([root, candidate]) == root and os.path.exists(candidate):
                path = candidate
        return Artifact(kind=kind, path=path, url=url)
