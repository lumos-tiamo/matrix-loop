from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    platform: str
    handle: str
    vertical: str | None = None
    positioning: str | None = None
    objective_weights: dict | None = None
    acceptance_criteria: str | None = None


class ImportSnapshotsIn(BaseModel):
    csv: str


class SetStatusIn(BaseModel):
    status: str


class SetReviewStatusIn(BaseModel):
    review_status: str


class AccountListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: str
    handle: str
    vertical: str | None
    positioning: str | None
    latest_followers: int | None
    latest_composite_score: float | None
    latest_loop_status: str | None
    source_tier: str | None


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    followers: int | None
    engagement_rate: float | None
    hit_rate: float | None
    conversions: int | None
    source_tier: str


class ContentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic: str | None
    views: int | None
    likes: int | None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    content: str
    status: str


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    content: str
    review_status: str
    parent_id: int | None = None


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    composite_score: float
    breakdown: dict
    created_at: datetime


class LoopRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    diagnosis: str | None
    verify_result: dict
    status: str
    tokens_cost: int | None = None
    evaluation: EvaluationOut | None
    recommendations: list[RecommendationOut]
    drafts: list[DraftOut]


class AccountDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: str
    handle: str
    vertical: str | None
    positioning: str | None
    objective_weights: dict | None = None
    snapshots: list[SnapshotOut]
    content_items: list[ContentItemOut]
    loop_runs: list[LoopRunOut]


class ContentLibraryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    account_handle: str
    platform: str
    topic: str | None
    views: int | None
    likes: int | None
    comments: int | None
    published_at: datetime | None


class SegmentCreate(BaseModel):
    label: str


class EndpointCreate(BaseModel):
    name: str
    url_pattern: str | None = None


class CompositionItem(BaseModel):
    segment_id: int
    weight: float = 1.0


class SetComposition(BaseModel):
    segments: list[CompositionItem]


class SetEndpoint(BaseModel):
    endpoint_id: int | None = None


class SetExternalRef(BaseModel):
    external_ref: str
    external_source: str | None = "aitoearn"


class SetBrief(BaseModel):
    main_direction: str
    sub_niches: list[str] = []
    tone: str | None = None
    language: str = "en"
    persona: str | None = None
    format: str = "faceless"
    compliance_stance: str = "info_education"
    target_seconds: int = 50


class GenerateVideoIn(BaseModel):
    script_draft_id: int


class VideoAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    script_draft_id: int | None
    provider: str
    media_url: str | None
    duration: float | None
    cost: float
    status: str
    review_status: str
    stage: str | None = None
    progress: int = 0
    created_at: datetime


class PalmierFinishIn(BaseModel):
    file_path: str   # absolute path, or a bare filename already in video_output_dir, of the Palmier export


class SetVideoReview(BaseModel):
    review_status: str


class PublishIn(BaseModel):
    video_asset_id: int
    caption: str | None = None
    publish_at: datetime | None = None


class SetAutopilot(BaseModel):
    enabled: bool


class PublishDispatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    video_asset_id: int | None
    aitoearn_flow_id: str | None
    aitoearn_task_id: str | None
    platform_work_id: str | None
    status: str
    publish_at: datetime | None
    media_urls: list[str]
    caption: str | None
    created_at: datetime


class TrendIn(BaseModel):
    source: str
    title: str
    url: str | None = None
    niche: str | None = None
    engagement: int | None = None
    distilled_topic: str | None = None
    score: float = 0.0


class TrendIngest(BaseModel):
    trends: list[TrendIn]
