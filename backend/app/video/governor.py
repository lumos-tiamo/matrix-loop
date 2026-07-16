from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, ChannelBrief, VideoAsset
from app.video.base import NearDuplicateScript, VideoQuotaExceeded
from app.video.guardrails import is_near_duplicate_script

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoConfig:
    max_videos_per_day: int = 20          # global across the whole matrix
    per_account_per_day: int = 2
    per_channel_per_day: int = 10         # per account.vertical (channel proxy)
    video_budget: float = 20.0            # cost/credit ceiling per batch
    max_concurrent: int = 2               # provider concurrency for batch generation
    confirm_threshold: int = 5            # batches larger than this need explicit confirmation
    dedup_similarity: float = 0.85        # cross-account near-duplicate script threshold


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _count_since(session: Session, start: datetime, *, account_id: int | None = None,
                 vertical: str | None = None, statuses: list[str] | None = None) -> int:
    stmt = select(func.count(VideoAsset.id)).where(VideoAsset.created_at >= start)
    if account_id is not None:
        stmt = stmt.where(VideoAsset.account_id == account_id)
    if vertical is not None:
        stmt = stmt.join(Account, Account.id == VideoAsset.account_id).where(Account.vertical == vertical)
    if statuses is not None:
        stmt = stmt.where(VideoAsset.status.in_(statuses))
    return int(session.scalar(stmt) or 0)


def _dedup_key(account_id: int, script: str, provider_name: str) -> str:
    raw = f"{account_id}|{script}|{provider_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def generate_video(session: Session, account, script_draft, *, provider,
                   brief=None, cfg: VideoConfig | None = None) -> VideoAsset:
    """Generate one governed video from an ADOPTED script draft. Layers, in order:
    human-gate -> dedup (reuse) -> cross-account differentiation -> daily quotas -> generate + meter.
    Raises ValueError (not adopted), NearDuplicateScript, or VideoQuotaExceeded to stop."""
    if cfg is None:
        from app.config import settings
        cfg = VideoConfig(
            max_videos_per_day=settings.video_max_per_day,
            per_account_per_day=settings.video_per_account_per_day,
            per_channel_per_day=settings.video_per_channel_per_day,
        )
    if getattr(script_draft, "review_status", None) != "adopted":
        raise ValueError("script draft must be adopted before video generation (human gate)")

    script = script_draft.content or ""
    if brief is None:
        brief = session.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account.id))

    # dedup: identical script for this account already produced a ready asset -> reuse
    dedup_key = _dedup_key(account.id, script, provider.name)
    existing = session.scalar(
        select(VideoAsset).where(
            VideoAsset.account_id == account.id,
            VideoAsset.dedup_key == dedup_key,
            VideoAsset.status == "ready",
        )
    )
    if existing is not None:
        return existing

    # differentiation: too similar to another account's recent script -> reject
    if is_near_duplicate_script(session, account.id, script, threshold=cfg.dedup_similarity):
        raise NearDuplicateScript(
            f"script too similar (>= {cfg.dedup_similarity}) to another account's recent video"
        )

    # NOTE: dedup + quota are check-then-act without locking — safe for the current single-worker deployment; needs SELECT FOR UPDATE or a unique constraint if run multi-worker.
    # daily quotas — count only non-failed rows (ready + generating) so failed attempts don't burn quota
    start = _today_start()
    if _count_since(session, start, statuses=["ready", "generating"]) >= cfg.max_videos_per_day:
        raise VideoQuotaExceeded(f"global daily cap {cfg.max_videos_per_day} reached")
    if _count_since(session, start, account_id=account.id, statuses=["ready", "generating"]) >= cfg.per_account_per_day:
        raise VideoQuotaExceeded(f"account daily cap {cfg.per_account_per_day} reached")
    if account.vertical is not None and \
            _count_since(session, start, vertical=account.vertical, statuses=["ready", "generating"]) >= cfg.per_channel_per_day:
        raise VideoQuotaExceeded(f"channel(vertical) daily cap {cfg.per_channel_per_day} reached")

    # generate + meter
    asset = VideoAsset(account_id=account.id, script_draft_id=script_draft.id,
                       provider=provider.name, dedup_key=dedup_key, status="generating")
    session.add(asset)
    # Commit the "generating" row BEFORE the (possibly slow — faceless is ~15-30s) generate() so we
    # do not hold a write transaction open across it. On SQLite a long-held write lock makes
    # concurrent writers (scheduler + a manual call, or two autopilot accounts) hit
    # "database is locked". expire_on_commit=False keeps `asset` usable after commit.
    session.commit()

    # Real progress: providers call on_progress(stage_label, pct) as they move through their
    # pipeline; we persist it on the (already-committed) row so the UI polls actual progress,
    # not a fake timer. Quick commits release the SQLite write lock immediately.
    def on_progress(stage: str, pct: int) -> None:
        try:
            asset.stage = (stage or "")[:48]
            asset.progress = max(0, min(99, int(pct)))
            session.commit()
        except Exception:  # noqa: BLE001 - progress reporting must never break generation
            session.rollback()

    try:
        result = provider.generate(script=script, brief=brief, params={
            "on_progress": on_progress,
            "account_handle": getattr(account, "handle", None),
            "account_id": account.id,
        })
    except Exception as exc:  # noqa: BLE001 - isolate provider failures
        asset.status = "failed"
        session.commit()
        logger.warning("video provider %s failed for account %s: %s", provider.name, account.id, exc)
        raise
    asset.media_url = result.media_url
    asset.duration = result.duration
    asset.cost = result.cost
    # We keep our account-scoped dedup_key (not result.dedup_key). A real provider's job/content id (result.dedup_key) is intentionally not persisted yet; add a provider_job_id column when wiring Seedance.
    asset.status = "ready"
    asset.stage = "done"
    asset.progress = 100
    session.commit()
    return asset


def estimate_batch(count: int, per_video_cost: float = 1.0) -> dict:
    """Pre-batch estimate for the confirmation gate."""
    return {"count": count, "estimated_cost": round(count * per_video_cost, 4)}


def run_video_batch(session: Session, pairs, *, provider, cfg: VideoConfig | None = None) -> dict:
    """Generate videos for (account, script_draft) pairs under the budget breaker.
    Per-item failures (not adopted, quota, near-duplicate, provider error) are isolated.
    Stops after the first video whose cumulative cost reaches or exceeds cfg.video_budget (inclusive ceiling).
    Commits per item on the shared session; not safe to call inside an outer transaction."""
    cfg = cfg or VideoConfig()
    generated = 0
    total_cost = 0.0
    errors: list[dict] = []
    stopped_early = False
    for account, draft in pairs:
        try:
            asset = generate_video(session, account, draft, provider=provider, cfg=cfg)
            generated += 1
            total_cost += asset.cost or 0.0
            if total_cost >= cfg.video_budget:
                stopped_early = True
                break
        except Exception as exc:  # noqa: BLE001 - isolate per-item failures
            errors.append({"account_id": account.id, "draft_id": getattr(draft, "id", None),
                           "error": str(exc)})
    return {"generated": generated, "total_cost": round(total_cost, 4),
            "errors": errors, "stopped_early": stopped_early}


def usage_summary(session: Session, *, cfg: VideoConfig | None = None) -> dict:
    """Daily + cumulative video usage for the dashboard."""
    cfg = cfg or VideoConfig()
    start = _today_start()
    today_count = _count_since(session, start, statuses=["ready"])
    today_cost = float(session.scalar(
        select(func.coalesce(func.sum(VideoAsset.cost), 0.0))
        .where(VideoAsset.created_at >= start)
        .where(VideoAsset.status == "ready")
    ) or 0.0)
    total_count = int(session.scalar(
        select(func.count(VideoAsset.id)).where(VideoAsset.status == "ready")
    ) or 0)
    total_cost = float(session.scalar(
        select(func.coalesce(func.sum(VideoAsset.cost), 0.0)).where(VideoAsset.status == "ready")
    ) or 0.0)
    return {
        "today_count": today_count,
        "today_cost": round(today_cost, 4),
        "total_count": total_count,
        "total_cost": round(total_cost, 4),
        "caps": {
            "max_videos_per_day": cfg.max_videos_per_day,
            "per_account_per_day": cfg.per_account_per_day,
            "per_channel_per_day": cfg.per_channel_per_day,
            "video_budget": cfg.video_budget,
        },
    }
