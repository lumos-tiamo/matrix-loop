from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_scheduler = None  # module-level BackgroundScheduler holder


def scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running


def start_scheduler(session_factory: Callable, interval_minutes: int | None = None,
                    max_accounts: int | None = None) -> None:
    """Idempotently build + start the unattended autopilot scheduler."""
    global _scheduler
    if scheduler_running():
        return
    from app.scheduler.runner import build_scheduler
    _scheduler = build_scheduler(session_factory, interval_minutes=interval_minutes, max_accounts=max_accounts)
    _scheduler.start()
    logger.info("unattended scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("unattended scheduler stopped")
    _scheduler = None
