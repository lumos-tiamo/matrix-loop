from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.scheduler.batch import run_batch

logger = logging.getLogger(__name__)


def _run_scheduled_batch(session_factory: Callable) -> None:
    session = session_factory()
    try:
        report = run_batch(session, sync=True)
        logger.info("scheduled batch: processed=%s looped=%s synced=%s errors=%s no_progress=%s",
                    report.processed, report.looped, report.synced, len(report.errors), len(report.no_progress))
    finally:
        session.close()


def build_scheduler(session_factory: Callable, interval_minutes: int | None = None) -> BackgroundScheduler:
    """Build (but do not start) a scheduler that runs run_batch every interval_minutes.
    Call .start() on the returned scheduler to begin unattended operation."""
    minutes = interval_minutes if interval_minutes is not None else settings.schedule_interval_minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_scheduled_batch, "interval", minutes=minutes,
                      args=[session_factory], id="matrixloop-batch", replace_existing=True)
    return scheduler
