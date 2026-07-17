from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_weights() -> dict:
    return {"growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25}


class Account(Base):
    __tablename__ = "accounts"
    # Fix #2: unique constraint on (platform, handle)
    __table_args__ = (UniqueConstraint("platform", "handle", name="uq_account_platform_handle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    handle: Mapped[str] = mapped_column(String(128), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), nullable=True)
    positioning: Mapped[str | None] = mapped_column(String, nullable=True)
    objective_weights: Mapped[dict] = mapped_column(JSON, default=_default_weights)
    acceptance_criteria: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    endpoint_id: Mapped[int | None] = mapped_column(ForeignKey("endpoints.id"), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    external_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    autopilot: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    content_items: Mapped[list["ContentItem"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    # Fix #7: back-reference for loop_runs
    loop_runs: Mapped[list["LoopRun"]] = relationship(back_populates="account", cascade="all, delete-orphan")

    # Fix #1: ensure JSON default is present on unsaved instances
    def __init__(self, **kw):
        kw.setdefault("objective_weights", _default_weights())
        super().__init__(**kw)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_tier: Mapped[str] = mapped_column(String(16), default="manual")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped["Account"] = relationship(back_populates="snapshots")

    # Fix #1: ensure extra is present on unsaved instances
    def __init__(self, **kw):
        kw.setdefault("extra", dict())
        super().__init__(**kw)


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (UniqueConstraint("account_id", "platform_post_id", name="uq_content_item_account_post"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_asset_id: Mapped[int | None] = mapped_column(ForeignKey("video_assets.id"), nullable=True, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True, index=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped["Account"] = relationship(back_populates="content_items")

    # Fix #1: ensure extra is present on unsaved instances
    def __init__(self, **kw):
        kw.setdefault("extra", dict())
        super().__init__(**kw)


class LoopRun(Base):
    __tablename__ = "loop_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    diagnosis: Mapped[str | None] = mapped_column(String, nullable=True)
    verify_result: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens_cost: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="ok")  # ok|no_progress|error|budget_stop

    # Fix #4: removed delete-orphan so Evaluation survives LoopRun deletion
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="loop_run", uselist=False)
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="loop_run", cascade="all, delete-orphan"
    )
    drafts: Mapped[list["Draft"]] = relationship(back_populates="loop_run", cascade="all, delete-orphan")
    # Fix #7: back-reference to Account
    account: Mapped["Account"] = relationship(back_populates="loop_runs")

    # Fix #1: ensure verify_result is present on unsaved instances
    def __init__(self, **kw):
        kw.setdefault("verify_result", dict())
        super().__init__(**kw)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    loop_run_id: Mapped[int | None] = mapped_column(ForeignKey("loop_runs.id"), nullable=True)
    composite_score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    loop_run: Mapped["LoopRun | None"] = relationship(back_populates="evaluation")

    # Fix #1: ensure breakdown is present on unsaved instances
    def __init__(self, **kw):
        kw.setdefault("breakdown", dict())
        super().__init__(**kw)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_run_id: Mapped[int] = mapped_column(ForeignKey("loop_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # positioning|content_direction|cadence|content_performance
    content: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|worked|failed|rejected

    loop_run: Mapped["LoopRun"] = relationship(back_populates="recommendations")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_run_id: Mapped[int] = mapped_column(ForeignKey("loop_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # topic|script
    content: Mapped[str] = mapped_column(String)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|rejected
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True, index=True)  # script -> its source topic

    loop_run: Mapped["LoopRun"] = relationship(back_populates="drafts")


class Endpoint(Base):
    __tablename__ = "endpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)          # 自定义出口，如 Nina / xaue
    url_pattern: Mapped[str | None] = mapped_column(String, nullable=True)  # bio 外链匹配子串
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AudienceSegment(Base):
    __tablename__ = "audience_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), unique=True)         # 自定义人群标签，如 海外投资者 / crypto


class AccountSegment(Base):
    __tablename__ = "account_segments"
    __table_args__ = (UniqueConstraint("account_id", "segment_id", name="uq_account_segment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("audience_segments.id"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)           # 该账号粉丝分到此人群的占比


class ChannelBrief(Base):
    __tablename__ = "channel_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), unique=True, index=True)
    main_direction: Mapped[str] = mapped_column(String(128))          # e.g. web3
    sub_niches: Mapped[list] = mapped_column(JSON, default=list)      # ["加密交易者", ...]
    tone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    persona: Mapped[str | None] = mapped_column(String(128), nullable=True)
    format: Mapped[str] = mapped_column(String(16), default="faceless")           # faceless|avatar
    compliance_stance: Mapped[str] = mapped_column(String(24), default="info_education")
    target_seconds: Mapped[int] = mapped_column(default=50, server_default="50", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __init__(self, **kw):
        kw.setdefault("sub_niches", list())
        super().__init__(**kw)


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    script_draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(String, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # account-scoped sha256[:32]; a real provider's job id would need its own column
    status: Mapped[str] = mapped_column(String(16), default="ready")              # generating|ready|failed
    review_status: Mapped[str] = mapped_column(String(16), default="pending")     # pending|approved|rejected
    stage: Mapped[str | None] = mapped_column(String(48), nullable=True)          # live pipeline stage label while generating
    progress: Mapped[int] = mapped_column(Integer, default=0)                     # 0-100 real progress while generating
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PublishDispatch(Base):
    __tablename__ = "publish_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    video_asset_id: Mapped[int | None] = mapped_column(ForeignKey("video_assets.id"), nullable=True, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True)
    aitoearn_flow_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    aitoearn_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_work_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")   # pending|queued|published|failed
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_urls: Mapped[list] = mapped_column(JSON, default=list)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __init__(self, **kw):
        kw.setdefault("media_urls", list())
        super().__init__(**kw)


class PublishPlan(Base):
    """Step-6 companion content for one video asset: the platform-native caption, hashtags,
    external-link placement (X=first_reply / IG=link_sticker_bio / TikTok=bio), and suggested
    posting time. Human-editable before dispatch; publish() prefers this over an ad-hoc caption.
    One plan per asset (upsert)."""
    __tablename__ = "publish_plans"
    __table_args__ = (UniqueConstraint("video_asset_id", name="uq_publish_plan_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    video_asset_id: Mapped[int] = mapped_column(ForeignKey("video_assets.id"), index=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    external_link_slot: Mapped[str | None] = mapped_column(String(32), nullable=True)  # first_reply|link_sticker_bio|bio
    external_link_text: Mapped[str | None] = mapped_column(String, nullable=True)
    posting_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")   # draft|ready
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)         # idea 来源(核实热点URL)
    source_score: Mapped[float | None] = mapped_column(Float, nullable=True)      # 真实性评估(0-100 置信度)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __init__(self, **kw):
        kw.setdefault("hashtags", list())
        super().__init__(**kw)


class AppState(Base):
    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)


class FlywheelEvent(Base):
    __tablename__ = "flywheel_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    cycle_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    step: Mapped[str] = mapped_column(String(16))                 # sync|evaluate|topic|script|video|publish|track
    status: Mapped[str] = mapped_column(String(12))               # ok|skipped|blocked|error
    detail: Mapped[str | None] = mapped_column(String, nullable=True)


class Trend(Base):
    __tablename__ = "trends"
    __table_args__ = (UniqueConstraint("source", "title", name="uq_trend_source_title"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(24))                       # tiktok|youtube|x|web
    title: Mapped[str] = mapped_column(String)                           # the viral piece / headline
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    niche: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    engagement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distilled_topic: Mapped[str | None] = mapped_column(String, nullable=True)  # LLM-distilled angle to make
    score: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class Calibration(Base):
    """One work = one blind prediction = one review (per-work calibration, borrowed from
    xiaobei's content-calibrator). Before publish we score the work against a platform-wide
    rubric AND blind-predict its metrics — both frozen at `locked_at`, immutable. At T+Nd we
    fill `actual` from real interaction data, compute `error`, and the aggregate feeds rubric
    evolution. `gate_passed` is the quality門 that guards publish."""
    __tablename__ = "calibrations"
    __table_args__ = (UniqueConstraint("video_asset_id", name="uq_calibration_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_asset_id: Mapped[int] = mapped_column(ForeignKey("video_assets.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    rubric_version: Mapped[str] = mapped_column(String(24))
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)          # 0-100 blind rubric score
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)               # per-dimension scores + notes
    predicted: Mapped[dict] = mapped_column(JSON, default=dict)               # {views, engagement_rate, ...} — immutable
    prediction_note: Mapped[str | None] = mapped_column(String, nullable=True)
    actual: Mapped[dict] = mapped_column(JSON, default=dict)                  # filled at review
    error: Mapped[dict] = mapped_column(JSON, default=dict)                   # per-metric signed % error
    calibration_error: Mapped[float | None] = mapped_column(Float, nullable=True)  # aggregate mean abs % error
    gate_passed: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="predicted")      # predicted|published|reviewed
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)  # prediction frozen
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __init__(self, **kw):
        for k in ("breakdown", "predicted", "actual", "error"):
            kw.setdefault(k, dict())
        super().__init__(**kw)
