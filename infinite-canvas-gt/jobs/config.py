"""作业层配置 —— 全部从环境变量读，带安全默认值。

同机部署默认：worker 打本机、回环免 token、产物回本地绝对路径。
"""

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class JobsConfig:
    # worker 回环调用的服务自身地址（同机）
    self_base_url: str = "http://127.0.0.1:3000"
    # 项目根目录，用于把 /assets/output/x.png 转成本地绝对路径
    base_dir: str = ""
    # SQLite 作业库路径
    db_path: str = ""
    # 同时执行的作业数
    concurrency: int = 3
    # 单个作业失败后的最大重试次数（指数退避）
    max_retries: int = 2
    # 每次轮询间隔（秒）与总超时（秒）
    poll_interval: float = 2.0
    job_timeout: float = 1800.0
    # worker 调用自身端点时携带的 token（若服务开了 APP_TOKEN 且 worker 走非回环，需要）
    app_token: str = ""

    @property
    def output_dir(self) -> str:
        return os.path.join(self.base_dir, "assets", "output")


def load_jobs_config(base_dir: str) -> JobsConfig:
    """从环境变量构造配置。base_dir 由 main.py 传入（= BASE_DIR）。"""
    port = _env_int("PORT", 3000)
    default_base = f"http://127.0.0.1:{port}"
    data_dir = os.path.join(base_dir, "data")
    return JobsConfig(
        self_base_url=os.getenv("JOBS_SELF_BASE_URL", default_base).rstrip("/"),
        base_dir=base_dir,
        db_path=os.getenv("JOBS_DB_PATH", os.path.join(data_dir, "jobs.db")),
        concurrency=_env_int("JOB_CONCURRENCY", 3),
        max_retries=_env_int("JOB_MAX_RETRIES", 2),
        poll_interval=float(_env_int("JOB_POLL_INTERVAL_MS", 2000)) / 1000.0,
        job_timeout=float(_env_int("JOB_TIMEOUT_SEC", 1800)),
        app_token=os.getenv("APP_TOKEN", ""),
    )
