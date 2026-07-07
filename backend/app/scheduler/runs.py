from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict

from app.scheduler.batch import BatchConfig, run_batch

logger = logging.getLogger(__name__)

# In-memory registry of batch runs (process-local; fine for single-worker ops).
BATCH_RUNS: dict[str, dict] = {}

_MAX_RUNS = 500


def record_run(run_id: str, entry: dict) -> None:
    """Write *entry* into BATCH_RUNS and evict the oldest entry when the cap is exceeded."""
    BATCH_RUNS[run_id] = entry
    if len(BATCH_RUNS) > _MAX_RUNS:
        # evict oldest inserted (dict preserves insertion order)
        oldest = next(iter(BATCH_RUNS))
        BATCH_RUNS.pop(oldest, None)


def new_run_id() -> str:
    return uuid.uuid4().hex


def start_batch(run_id: str, session_factory: Callable, *, sync: bool = True,
                batch_cfg: BatchConfig | None = None) -> None:
    # Initial "running" state is pre-seeded by the route (single owner); start_batch
    # only writes the terminal completed/error state.
    session = session_factory()
    try:
        report = run_batch(session, sync=sync, batch_cfg=batch_cfg)
        record_run(run_id, {"status": "completed", "report": asdict(report), "error": None})
    except Exception as exc:  # noqa: BLE001 - record failure, don't crash the worker
        logger.exception("async batch %s failed", run_id)
        record_run(run_id, {"status": "error", "report": None, "error": str(exc)})
    finally:
        session.close()
