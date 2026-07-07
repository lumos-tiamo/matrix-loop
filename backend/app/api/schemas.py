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
