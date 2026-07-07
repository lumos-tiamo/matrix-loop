# MatrixLoop 调度 / 生产化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「十几个手动跑」变成「无人值守批量跑」：一个批量编排器 `run_batch` 对所有账号（可选）先 sync 再 run_loop，带账号级隔离、批量上限、连续错误熔断、no_progress 汇总；一个 APScheduler 定时器周期触发；一个 `POST /batch/run` 按需触发。

**Architecture:** `app/scheduler/batch.py` - `run_batch(session, *, sync, batch_cfg, loop_cfg, scoring_cfg) -> BatchReport`：遍历账号，逐个（可选）sync（自动连接器才 sync，manual 跳过，sync 失败不致命）再 run_loop；每账号异常隔离（记录进 report.errors，继续下一个）；`max_accounts` 限批量、`stop_after_consecutive_errors` 熔断（LLM/API 全挂时别烧完 500）。`app/scheduler/runner.py` - `build_scheduler(session_factory, interval_minutes)` 用 APScheduler BackgroundScheduler 注册周期 job。API `POST /batch/run` 按需触发。真实 token 成本上限待 LLMClient 暴露 usage（现 tokens_cost=0，熔断用连续错误计数，是当前唯一有意义的护栏）。

**Tech Stack:** Python 3.13（同一 venv），新增 `apscheduler` (3.x)，pytest。

**依赖：** plan 4（`run_loop`）、plan 7（`resolve_connector`, `sync_account`）、plan 5 API。

---

### Task 1: run_batch 编排器（仅 loop）+ 护栏

**Files:**
- Create: `backend/app/scheduler/__init__.py`, `backend/app/scheduler/batch.py`
- Test: `backend/tests/test_batch.py`

- [ ] **Step 1: 写失败的批量测试**

Create `backend/tests/test_batch.py`:
```python
from datetime import datetime, timezone

import app.scheduler.batch as batch_mod
from app.models import Account, Snapshot, LoopRun
from app.scheduler.batch import run_batch, BatchConfig


def _acct(session, handle, followers=(100000, 110000)):
    acc = Account(platform="twitter", handle=handle, objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    for i, f in enumerate(followers):
        session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1 + i * 2, tzinfo=timezone.utc), followers=f))
    session.commit()
    return acc


def test_run_batch_loops_all_accounts(session):
    _acct(session, "@a1"); _acct(session, "@a2"); _acct(session, "@a3")
    report = run_batch(session, sync=False)
    assert report.processed == 3
    assert report.looped == 3
    assert report.errors == []
    assert session.query(LoopRun).count() == 3


def test_run_batch_isolates_per_account_error(session, monkeypatch):
    a1 = _acct(session, "@a1"); a2 = _acct(session, "@a2"); a3 = _acct(session, "@a3")
    real = batch_mod.run_loop

    def flaky(sess, account, **kw):
        if account.id == a2.id:
            raise RuntimeError("boom")
        return real(sess, account, **kw)

    monkeypatch.setattr(batch_mod, "run_loop", flaky)
    report = run_batch(session, sync=False)
    assert report.processed == 3
    assert report.looped == 2                       # a1, a3 succeeded
    assert len(report.errors) == 1
    assert report.errors[0]["account_id"] == a2.id
    assert report.errors[0]["stage"] == "loop"


def test_run_batch_max_accounts_caps(session):
    for i in range(5):
        _acct(session, f"@a{i}")
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(max_accounts=2))
    assert report.processed == 2
    assert report.looped == 2


def test_run_batch_collects_no_progress(session):
    acc = Account(platform="twitter", handle="@flat", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()
    # run 3 prior batches to build flat history, then the 4th flags no_progress
    for _ in range(4):
        report = run_batch(session, sync=False)
    assert acc.id in report.no_progress


def test_run_batch_circuit_breaker(session, monkeypatch):
    for i in range(6):
        _acct(session, f"@a{i}")

    def always_fail(sess, account, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(batch_mod, "run_loop", always_fail)
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(stop_after_consecutive_errors=3))
    assert report.stopped_early is True
    assert len(report.errors) == 3           # stopped after 3 consecutive
    assert report.processed == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_batch.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.scheduler'`

- [ ] **Step 3: 实现 run_batch（仅 loop 路径；sync 分支在 Task 2 接入）**

Create `backend/app/scheduler/__init__.py` (空文件).

Create `backend/app/scheduler/batch.py`:
```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_batch.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/scheduler backend/tests/test_batch.py
git commit -m "feat(scheduler): run_batch orchestrator - loop all accounts, isolation, max_accounts, circuit breaker, no_progress"
```

---

### Task 2: sync 接入 run_batch

**Files:**
- Modify: `backend/app/scheduler/batch.py` (实现 `_try_sync`)
- Test: `backend/tests/test_batch_sync.py`

- [ ] **Step 1: 写失败的 sync 批量测试**

Create `backend/tests/test_batch_sync.py`:
```python
from datetime import datetime, timezone

import app.scheduler.batch as batch_mod
from app.models import Account, Snapshot
from app.connectors.base import ConnectorResult
from app.scheduler.batch import run_batch


def _acct(session, platform, handle):
    acc = Account(platform=platform, handle=handle, objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=1100),
    ])
    session.commit()
    return acc


def test_batch_syncs_auto_and_skips_manual(session, monkeypatch):
    _acct(session, "twitter", "@auto")      # has auto connector
    _acct(session, "xiaohongshu", "@manual")  # manual -> skipped, no error

    class FakeConnector:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 2000}], content=[])

    def fake_resolve(platform, cfg=None):
        return (FakeConnector(), "api") if platform == "twitter" else (None, "manual")

    monkeypatch.setattr(batch_mod, "resolve_connector", fake_resolve)
    report = run_batch(session, sync=True)

    assert report.processed == 2
    assert report.looped == 2         # both still loop
    assert report.synced == 1         # only the twitter account synced
    assert report.errors == []        # manual skip is not an error


def test_batch_sync_error_is_nonfatal(session, monkeypatch):
    _acct(session, "twitter", "@auto")

    class BrokenConnector:
        tier = "api"
        def fetch(self, account):
            raise RuntimeError("api down")

    monkeypatch.setattr(batch_mod, "resolve_connector", lambda platform, cfg=None: (BrokenConnector(), "api"))
    report = run_batch(session, sync=True)

    assert report.processed == 1
    assert report.looped == 1                          # loop still runs on existing data
    assert any(e["stage"] == "sync" for e in report.errors)  # sync error recorded, non-fatal
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_batch_sync.py -v`
Expected: FAIL - synced == 0 (sync is a no-op placeholder)

- [ ] **Step 3: 实现 _try_sync**

In `backend/app/scheduler/batch.py`, add these imports at the top (with the others):
```python
from app.connectors.registry import resolve_connector
from app.connectors.sync import sync_account
```

Replace the placeholder `_try_sync` with:
```python
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
```

Note: the test monkeypatches `batch_mod.resolve_connector`, so `_try_sync` MUST call the module-level `resolve_connector` name imported into batch.py.

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_batch_sync.py tests/test_batch.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/scheduler/batch.py backend/tests/test_batch_sync.py
git commit -m "feat(scheduler): batch sync integration - auto-sync connectors, skip manual, non-fatal sync errors"
```

---

### Task 3: APScheduler 定时器

**Files:**
- Modify: `backend/requirements.txt` (追加 apscheduler)
- Modify: `backend/app/config.py` (追加 interval 配置)
- Create: `backend/app/scheduler/runner.py`
- Test: `backend/tests/test_scheduler_runner.py`

- [ ] **Step 1: 追加依赖并安装**

Modify `backend/requirements.txt` — append:
```
APScheduler>=3.10,<4
```
Run: `cd backend && . .venv/bin/activate && pip install -q 'APScheduler>=3.10,<4' && python -c "import apscheduler; print('ok')"`
Expected: 打印 `ok`

- [ ] **Step 2: 追加配置**

Modify `backend/app/config.py` — add inside `Settings` (after `scrapecreators_api_key`):
```python
    schedule_interval_minutes: int = 360
```

- [ ] **Step 3: 写失败的 runner 测试**

Create `backend/tests/test_scheduler_runner.py`:
```python
from app.scheduler.runner import build_scheduler


def test_build_scheduler_registers_one_job():
    called = {}

    def fake_session_factory():
        raise AssertionError("should not be called at build time")

    scheduler = build_scheduler(fake_session_factory, interval_minutes=15)
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        # interval trigger reflects the configured minutes
        assert "15" in str(jobs[0].trigger) or jobs[0].trigger.interval.total_seconds() == 15 * 60
    finally:
        scheduler.shutdown(wait=False)
    assert called == {}  # session factory not invoked merely by building
```

- [ ] **Step 4: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_scheduler_runner.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.scheduler.runner'`

- [ ] **Step 5: 实现 runner**

Create `backend/app/scheduler/runner.py`:
```python
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
```

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_scheduler_runner.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/requirements.txt backend/app/config.py backend/app/scheduler/runner.py backend/tests/test_scheduler_runner.py
git commit -m "feat(scheduler): APScheduler interval runner for unattended batch runs"
```

---

### Task 4: API POST /batch/run

**Files:**
- Modify: `backend/app/api/routes.py` (追加 batch 路由)
- Test: `backend/tests/test_api_batch.py`

- [ ] **Step 1: 写失败的 batch 端点测试**

Create `backend/tests/test_api_batch.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, LoopRun


def test_batch_run_endpoint(client, session):
    for h in ("@b1", "@b2"):
        acc = Account(platform="xiaohongshu", handle=h, objective_weights={
            "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc)
        session.commit()
        session.add_all([
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
        ])
        session.commit()

    # sync=false via query param so manual platforms don't need connectors
    resp = client.post("/batch/run?sync=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 2
    assert body["looped"] == 2
    assert body["errors"] == []
    assert session.query(LoopRun).count() == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_batch.py -v`
Expected: FAIL - 404/405 (route missing)

- [ ] **Step 3: 追加 batch 路由**

Add to the top imports of `backend/app/api/routes.py`:
```python
from dataclasses import asdict

from app.scheduler.batch import run_batch
```

Append to `backend/app/api/routes.py`:
```python
@router.post("/batch/run")
def batch_run(sync: bool = True, db: Session = Depends(get_db)) -> dict:
    report = run_batch(db, sync=sync)
    return asdict(report)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_batch.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（此前 89 + 本计划 8 = 97 passed）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/tests/test_api_batch.py
git commit -m "feat(api): POST /batch/run triggers an on-demand batch (sync + loop over accounts)"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（此前 89 + 本计划 8 = 97）
- `run_batch` 遍历账号、（可选）先 sync 再 run_loop、账号级隔离、`max_accounts` 分批、连续错误熔断、汇总 no_progress
- `build_scheduler` 注册周期 job（APScheduler），`.start()` 即无人值守
- `POST /batch/run?sync=true|false` 按需触发并返回报告
- 备注：真实 token 成本上限待 LLMClient 暴露 usage 后接入（当前 tokens_cost=0，熔断以连续错误计数为准）；500 账号可用 max_accounts 分批 + 并发（并发留待需要时）
- 这是完整体的最后一块：地基 → 评估/分析 → 自我修正 Loop → API → Dashboard → 连接器 → 调度，全链路打通
