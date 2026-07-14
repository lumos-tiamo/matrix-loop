"""作业路由 —— 把 (type, provider) 映射到「用哪个现有端点提交」。

策略 (strategy)：
- image      → POST /api/canvas-image-tasks（按 provider_id 路由 ms/jimeng/volc/openai/gemini）
- video      → POST /api/canvas-video（jimeng 返回 submit_id 再轮询 query-media）
- runninghub → POST /api/runninghub/workflow-submit + GET /api/runninghub/query
- comfyui    → POST /api/canvas-comfy-tasks + GET /api/canvas-comfy-tasks/{id}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .models import VIDEO_TYPES, JobSpec, JobType

# 未显式指定 provider 时的默认路由
DEFAULT_PROVIDER = {
    JobType.TEXT_TO_IMAGE: "modelscope",
    JobType.IMAGE_TO_IMAGE: "modelscope",
    JobType.TEXT_TO_VIDEO: "jimeng",
    JobType.IMAGE_TO_VIDEO: "jimeng",
}

# 主力失败后的降级链（worker 依次尝试）
DEFAULT_FALLBACKS = {
    JobType.TEXT_TO_VIDEO: ["runninghub"],
    JobType.IMAGE_TO_VIDEO: ["runninghub"],
}


@dataclass(frozen=True)
class RoutePlan:
    provider: str  # 归一化后的最终 provider
    strategy: str  # image | video | runninghub | comfyui
    fallbacks: List[str] = field(default_factory=list)


def _strategy_for(provider: str, job_type: JobType) -> str:
    if provider == "runninghub":
        return "runninghub"
    if provider == "comfyui":
        return "comfyui"
    if job_type in VIDEO_TYPES:
        return "video"
    return "image"


class JobRouter:
    """无状态路由器；可注入自定义默认/降级表（供测试或配置覆盖）。"""

    def __init__(self, defaults=None, fallbacks=None):
        self._defaults = dict(DEFAULT_PROVIDER)
        if defaults:
            self._defaults.update(defaults)
        self._fallbacks = dict(DEFAULT_FALLBACKS)
        if fallbacks:
            self._fallbacks.update(fallbacks)

    def resolve(self, spec: JobSpec) -> RoutePlan:
        provider = spec.provider or self._defaults[spec.type]
        strategy = _strategy_for(provider, spec.type)
        # 降级链：去掉与主力相同的项，并只保留对该 type 合理的 provider
        raw_fallbacks = self._fallbacks.get(spec.type, [])
        fallbacks = [p for p in raw_fallbacks if p != provider]
        return RoutePlan(provider=provider, strategy=strategy, fallbacks=fallbacks)
