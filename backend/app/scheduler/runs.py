from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict

from app.scheduler.batch import BatchConfig, run_batch

logger = logging.getLogger(__name__)

# In-memory registry of batch runs (process-local; fine for single-worker ops).
BATCH_RUNS: dict[str, dict] = {}


def new_run_id() -> str:
    return uuid.uuid4().hex


def start_batch(run_id: str, session_factory: Callable, *, sync: bool = True,
                batch_cfg: BatchConfig | None = None) -> None:
    BATCH_RUNS[run_id] = {"status": "running", "report": None, "error": None}
    session = session_factory()
    try:
        report = run_batch(session, sync=sync, batch_cfg=batch_cfg)
        BATCH_RUNS[run_id] = {"status": "completed", "report": asdict(report), "error": None}
    except Exception as exc:  # noqa: BLE001 - record failure, don't crash the worker
        logger.exception("async batch %s failed", run_id)
        BATCH_RUNS[run_id] = {"status": "error", "report": None, "error": str(exc)}
    finally:
        session.close()
