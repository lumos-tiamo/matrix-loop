from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_weights() -> dict:
    return {"growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25}


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    handle: Mapped[str] = mapped_column(String(128), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), nullable=True)
    positioning: Mapped[str | None] = mapped_column(String, nullable=True)
    objective_weights: Mapped[dict] = mapped_column(JSON, default=_default_weights)
    acceptance_criteria: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="account", cascade="all, delete-orphan")


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
