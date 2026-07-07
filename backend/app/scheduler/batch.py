from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import resolve_connector
from app.connectors.sync import sync_account
from app.loop.engine import run_loop
from app.models import Account

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchConfig:
    max_accounts: int | None = None            # 每批最多处理多少账号（分批扫 500）
    offset: int = 0                            # 公平轮转起始索引（按 id 排序后跳过前 N 个）
    stop_after_consecutive_errors: int = 5     # 连续 N 个账号出错就熔断（别烧完整批）
    token_budget: int | None = None            # 累计 token 上限；超出则 stopped_early=True


@dataclass
class BatchReport:
    processed: int = 0
    synced: int = 0
    looped: int = 0
    no_progress: list[int] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    stopped_early: bool = False
    total_tokens: int = 0


def run_batch(session: Session, *, sync: bool = True, batch_cfg: BatchConfig | None = None,
              loop_cfg=None, scoring_cfg=None) -> BatchReport:
    batch_cfg = batch_cfg or BatchConfig()
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())
    accounts = accounts[batch_cfg.offset:]
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
            report.total_tokens += run.tokens_cost or 0
            if batch_cfg.token_budget is not None and report.total_tokens > batch_cfg.token_budget:
                report.stopped_early = True
                break
        except Exception as exc:  # noqa: BLE001 - isolate per-account failures
            logger.warning("batch loop failed for account %s: %s", acc.id, exc)
            report.errors.append({"account_id": acc.id, "stage": "loop", "error": str(exc)})
            consecutive_errors += 1
            if consecutive_errors >= batch_cfg.stop_after_consecutive_errors:
                report.stopped_early = True
                break

    return report


def _try_sync(session: Session, account: Account, report: BatchReport) -> None:
    """Best-effort sync via the account's auto connector. Manual platforms are skipped
    (not an error). A sync failure is non-fatal - the loop still runs on existing data."""
    connector, _tier = resolve_connector(account.platform)
    if connector is None:
        return  # manual-only platform: nothing to auto-sync
    try:
        sync_account(session, account, connector=connector)
        report.synced += 1
    except Exception as exc:  # noqa: BLE001 - sync failure must not abort the account's loop
        logger.warning("batch sync failed for account %s: %s", account.id, exc)
        report.errors.append({"account_id": account.id, "stage": "sync", "error": str(exc)})
