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
    kind: Mapped[str] = mapped_column(String(24))  # positioning|content_direction|cadence
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

    loop_run: Mapped["LoopRun"] = relationship(back_populates="drafts")
