"""作业层的数据契约 —— 对 loop 稳定，与各家 provider 解耦。"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class JobType(str, enum.Enum):
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
)

JOB_TYPES = frozenset(t.value for t in JobType)
PROVIDERS = frozenset(
    {"modelscope", "jimeng", "volcengine", "openai", "gemini", "runninghub", "comfyui"}
)
ARTIFACT_KINDS = frozenset({"image", "video"})

# 需要参考图/输入图的作业类型
INPUT_IMAGE_TYPES = frozenset({JobType.IMAGE_TO_IMAGE, JobType.IMAGE_TO_VIDEO})
VIDEO_TYPES = frozenset({JobType.TEXT_TO_VIDEO, JobType.IMAGE_TO_VIDEO})


class JobSpec(BaseModel):
    """单个作业的提交规格 —— loop 填这个。"""

    type: JobType
    prompt: str = Field(min_length=1, max_length=8000)
    provider: Optional[str] = Field(
        default=None,
        description="不填则按 type 走默认路由；可选值见 PROVIDERS",
    )
    input_image: Optional[str] = Field(
        default=None,
        description="i2i / i2v 的输入图：本地 /assets/* 路径、http(s) URL 或 data: URL",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="透传给引擎的参数：model/size/n/duration/aspect_ratio/resolution/workflowId/workflow_json 等",
    )
    client_ref: Optional[str] = Field(
        default=None, max_length=200, description="你的关联ID，用于幂等/回填"
    )

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v and v not in PROVIDERS:
            raise ValueError(f"provider 必须是 {sorted(PROVIDERS)} 之一，收到 {v!r}")
        return v or None

    def model_post_init(self, __context: Any) -> None:
        if self.type in INPUT_IMAGE_TYPES and not self.input_image:
            raise ValueError(f"{self.type.value} 需要 input_image")


class JobSubmit(BaseModel):
    """批量提交请求体。"""

    jobs: List[JobSpec] = Field(min_length=1, max_length=100)


class Artifact(BaseModel):
    kind: str  # image | video
    path: Optional[str] = None  # 本地绝对路径（同机模式）
    url: Optional[str] = None  # 服务内可访问 URL（/assets/output/...）
    meta: Dict[str, Any] = Field(default_factory=dict)


class JobRecord(BaseModel):
    """作业的完整状态 —— GET /api/jobs/{id} 返回这个。"""

    job_id: str
    batch_id: str
    client_ref: Optional[str] = None
    type: JobType
    provider: str
    status: JobStatus
    progress: float = 0.0
    artifacts: List[Artifact] = Field(default_factory=list)
    error: Optional[str] = None
    attempts: int = 0
    created_at: float
    updated_at: float
