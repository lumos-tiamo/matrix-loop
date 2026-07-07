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


class AccountListItem(BaseModel):
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
    objective_weights: dict
    snapshots: list[SnapshotOut]
    content_items: list[ContentItemOut]
    loop_runs: list[LoopRunOut]
