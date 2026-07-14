"""asyncio 执行器池 —— 领取 queued 作业、按路由执行、失败降级+重试、更新状态。

同机部署下这是「队列之上的队列」：现有端点自身也异步，本层额外提供统一契约、
批量、重启持久化、重试、provider 降级、client_ref 关联。
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from .client import JobCanceled, JobClient, JobExecutionError
from .config import JobsConfig
from .models import JobSpec, JobStatus
from .routing import JobRouter, RoutePlan, _strategy_for
from .store import JobStore

logger = logging.getLogger("jobs.worker")


class WorkerPool:
    def __init__(
        self,
        store: JobStore,
        router: JobRouter,
        client: JobClient,
        config: JobsConfig,
        idle_interval: float = 0.5,
    ):
        self._store = store
        self._router = router
        self._client = client
        self._cfg = config
        self._idle = idle_interval
        self._stop = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> int:
        """启动前先做崩溃恢复，再拉起 N 个 worker 协程。返回恢复的作业数。"""
        recovered = await asyncio.to_thread(self._store.recover_stuck)
        if recovered:
            logger.info("崩溃恢复：%d 个 running 作业重新入队", recovered)
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._worker_loop(i)) for i in range(self._cfg.concurrency)
        ]
        logger.info("作业执行器已启动，并发=%d", self._cfg.concurrency)
        return recovered

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks = []

    async def _worker_loop(self, idx: int) -> None:
        while not self._stop.is_set():
            try:
                claimed = await asyncio.to_thread(self._store.claim_next)
            except Exception:  # noqa: BLE001 - DB 抖动不应打死 worker
                logger.exception("claim_next 失败")
                await asyncio.sleep(self._idle)
                continue
            if claimed is None:
                await asyncio.sleep(self._idle)
                continue
            try:
                await self._execute(claimed)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - 兜底，防止单作业异常杀死 worker
                logger.exception("执行作业 %s 时未捕获异常", claimed.get("job_id"))
                await asyncio.to_thread(
                    self._store.set_failed, claimed["job_id"], "internal worker error"
                )

    async def _execute(self, claimed: dict) -> None:
        job_id = claimed["job_id"]
        spec: JobSpec = claimed["spec"]
        attempts = claimed["attempts"]
        plan = self._router.resolve(spec)
        providers = [plan.provider] + plan.fallbacks

        async def progress(p: float) -> None:
            await asyncio.to_thread(self._store.set_progress, job_id, p)

        async def cancel_check() -> bool:
            rec = await asyncio.to_thread(self._store.get, job_id)
            return rec is not None and rec.status == JobStatus.CANCELED

        last_err: Optional[str] = None
        for prov in providers:
            if await cancel_check():
                logger.info("作业 %s 已取消", job_id)
                return
            sub_plan = RoutePlan(
                provider=prov, strategy=_strategy_for(prov, spec.type), fallbacks=[]
            )
            try:
                artifacts = await self._client.run(sub_plan, spec, progress, cancel_check)
                await asyncio.to_thread(self._store.set_succeeded, job_id, artifacts)
                if prov != plan.provider:
                    logger.info("作业 %s 主力失败，降级到 %s 成功", job_id, prov)
                return
            except JobCanceled:
                logger.info("作业 %s 执行途中取消", job_id)
                return
            except JobExecutionError as e:
                last_err = f"[{prov}] {e}"
                logger.warning("作业 %s 走 %s 失败：%s", job_id, prov, e)
                continue

        # 本轮（含降级）全失败：按 max_retries 决定重试还是判死
        if attempts <= self._cfg.max_retries:
            await asyncio.to_thread(
                self._store.requeue, job_id, f"attempt {attempts} failed: {last_err}"
            )
            logger.info("作业 %s 第 %d 次失败，重新入队", job_id, attempts)
        else:
            await asyncio.to_thread(
                self._store.set_failed, job_id, last_err or "unknown error"
            )
            logger.error("作业 %s 超过重试上限，判失败", job_id)
