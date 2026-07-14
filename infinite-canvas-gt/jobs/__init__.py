"""统一「内容作业」层 —— 把 Infinite-Canvas-GT 变成无头生成服务。

对外只暴露一个稳定契约（POST /api/jobs → GET /api/jobs/{id}），
各家 provider 的差异全部藏在 adapter 后面。作业层自包含，不 import main.py：
worker 通过回环 HTTP 复用现有 139 个端点，产物统一回本地绝对路径。
"""

from .config import JobsConfig, load_jobs_config
from .models import (
    ARTIFACT_KINDS,
    JOB_TYPES,
    PROVIDERS,
    Artifact,
    JobRecord,
    JobSpec,
    JobStatus,
    JobSubmit,
    JobType,
)
from .store import JobStore
from .routing import JobRouter, RoutePlan

__all__ = [
    "JobsConfig",
    "load_jobs_config",
    "Artifact",
    "JobRecord",
    "JobSpec",
    "JobStatus",
    "JobSubmit",
    "JobType",
    "JobStore",
    "JobRouter",
    "RoutePlan",
    "JOB_TYPES",
    "PROVIDERS",
    "ARTIFACT_KINDS",
]
