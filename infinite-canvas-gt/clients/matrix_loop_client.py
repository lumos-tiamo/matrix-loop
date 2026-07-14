"""matrix-loop 侧的内容作业客户端 —— 同机调用 Infinite-Canvas-GT 无头服务。

把这个文件 import 进 matrix-loop（或复制过去），loop 只需三行就能出图/出视频：

    from matrix_loop_client import ContentClient
    client = ContentClient()                       # 默认 http://127.0.0.1:3000（回环免 token）
    arts = client.generate("a cyberpunk host", type="text_to_image")
    print(arts[0]["path"])                          # 本地绝对路径，直接喂给下游

零第三方依赖（只用标准库 urllib），不会给 matrix-loop 引入新依赖。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

TERMINAL = {"succeeded", "failed", "canceled"}


class JobError(RuntimeError):
    pass


class ContentClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:3000",
        app_token: str = "",
        poll_interval: float = 2.0,
        timeout: float = 1800.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.app_token = app_token
        self.poll_interval = poll_interval
        self.timeout = timeout

    # ---- 底层 HTTP（标准库）----

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = self.base_url + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.app_token:
            req.add_header("X-App-Token", self.app_token)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise JobError(f"{method} {path} -> {e.code}: {e.read().decode()[:300]}") from e

    # ---- 高层 API ----

    def submit(self, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """提交一批作业，立即返回 {batch_id, jobs:[{job_id, ...}]}。

        每个 job: {type, prompt, provider?, input_image?, params?, client_ref?}
        """
        return self._request("POST", "/api/jobs", {"jobs": jobs})

    def get(self, job_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/jobs/{job_id}")

    def wait(self, job_id: str) -> Dict[str, Any]:
        """阻塞轮询单个作业到终态，返回完整记录。"""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            rec = self.get(job_id)
            if rec["status"] in TERMINAL:
                return rec
            time.sleep(self.poll_interval)
        raise JobError(f"作业 {job_id} 轮询超时")

    def wait_batch(self, job_ids: List[str]) -> List[Dict[str, Any]]:
        return [self.wait(jid) for jid in job_ids]

    def generate(
        self,
        prompt: str,
        type: str = "text_to_image",
        provider: Optional[str] = None,
        input_image: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        client_ref: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """便捷方法：提交单个作业、等完成、返回 artifacts（失败抛 JobError）。"""
        job: Dict[str, Any] = {"type": type, "prompt": prompt}
        if provider:
            job["provider"] = provider
        if input_image:
            job["input_image"] = input_image
        if params:
            job["params"] = params
        if client_ref:
            job["client_ref"] = client_ref
        submitted = self.submit([job])
        rec = self.wait(submitted["jobs"][0]["job_id"])
        if rec["status"] != "succeeded":
            raise JobError(f"作业失败: {rec.get('error')}")
        return rec["artifacts"]


if __name__ == "__main__":
    # 手动冒烟：需要服务已启动 + 已配置 MODELSCOPE_API_KEY
    c = ContentClient()
    arts = c.generate("a serene mountain lake at dawn, cinematic", type="text_to_image")
    for a in arts:
        print(a["kind"], "->", a.get("path") or a.get("url"))
