from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.loop.engine import run_loop
from app.models import Account

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchConfig:
    max_accounts: int | None = None            # 每批最多处理多少账号（分批扫 500）
    stop_after_consecutive_errors: int = 5     # 连续 N 个账号出错就熔断（别烧完整批）


@dataclass
class BatchReport:
    processed: int = 0
    synced: int = 0
    looped: int = 0
    no_progress: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    stopped_early: bool = False


def run_batch(session: Session, *, sync: bool = True, batch_cfg: BatchConfig | None = None,
              loop_cfg=None, scoring_cfg=None) -> BatchReport:
    batch_cfg = batch_cfg or BatchConfig()
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())
    if batch_cfg.max_accounts is not None:
        accounts = accounts[: batch_cfg.max_accounts]

    report = BatchReport()
    consecutive_errors = 0

    for acc in accounts:
        report.processed += 1

        if sync:
            _try_sync(session, acc, report)

        try:
            run = run_loop(session, acc, cfg=loop_cfg, scoring_cfg=scoring_cfg)
            report.looped += 1
            consecutive_errors = 0
            if run.status == "no_progress":
                report.no_progress.append(acc.id)
        except Exception as exc:  # noqa: BLE001 - isolate per-account failures
            logger.warning("batch loop failed for account %s: %s", acc.id, exc)
            report.errors.append({"account_id": acc.id, "stage": "loop", "error": str(exc)})
            consecutive_errors += 1
            if consecutive_errors >= batch_cfg.stop_after_consecutive_errors:
                report.stopped_early = True
                break

    return report


def _try_sync(session: Session, account: Account, report: BatchReport) -> None:
    """Sync placeholder - filled in Task 2. No-op for now (loop-only batches)."""
    return None
