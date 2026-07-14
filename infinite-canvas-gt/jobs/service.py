"""作业服务装配 —— 把 store/router/client/worker 组装成单例。

main.py 只需三步接入：
    from jobs.service import JobService
    job_service = JobService(BASE_DIR)
    app.include_router(job_service.api_router)
    # 并在 startup/shutdown 事件里 await job_service.start() / stop()
"""

from __future__ import annotations

import logging

from .api import create_jobs_router
from .client import JobClient
from .config import load_jobs_config
from .routing import JobRouter
from .store import JobStore
from .worker import WorkerPool

logger = logging.getLogger("jobs.service")


class JobService:
    def __init__(self, base_dir: str):
        self.config = load_jobs_config(base_dir)
        self.store = JobStore(self.config.db_path)
        self.router = JobRouter()
        self.client = JobClient(self.config)
        self.worker = WorkerPool(self.store, self.router, self.client, self.config)
        self.api_router = create_jobs_router(self.store, self.router)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.worker.start()
        self._started = True
        logger.info(
            "JobService 就绪 | db=%s | 回环=%s | 并发=%d",
            self.config.db_path,
            self.config.self_base_url,
            self.config.concurrency,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        await self.worker.stop()
        await self.client.aclose()
        self.store.close()
        self._started = False
