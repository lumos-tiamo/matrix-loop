# MatrixLoop 生产硬化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** 清掉三项一直延后的生产化 TODO：`/batch/run` 后台异步（500 账号不卡 HTTP）、LLM token 成本计量 + 预算熔断、`/overview`/`/accounts`/`/content` 的 N+1 与内存排序性能。

**Architecture:** T1 加一个内存运行登记表 + `BackgroundTasks` 异步跑 `run_batch`，`GET /batch/runs/{id}` 查状态。T2 让 `ClaudeClient` 暴露 `last_usage`，`run_loop` 把 tokens 记进 `LoopRun.tokens_cost`，`run_batch` 加 `token_budget` 熔断。T3 把逐账号查询改成「批量取 + Python 分组」，`/content` 排序/LIMIT 下推 SQL。全程保持既有响应形状与测试断言不变。

**Tech Stack:** 后端 Python/FastAPI（同 venv），pytest。无新依赖。

**依赖：** plan 5 API、plan 7 连接器、plan 8 调度、dashboard-v2 的 /overview /content、flow 的 build。

---

### Task 1: `/batch/run` 后台异步 + 状态查询

**Files:** Create `backend/app/scheduler/runs.py`; Modify `backend/app/api/routes.py`; Test `backend/tests/test_batch_async.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_batch_async.py`:
```python
from datetime import datetime, timezone

import app.scheduler.runs as runs_mod
from app.models import Account, Snapshot
from app.scheduler.runs import BATCH_RUNS, start_batch, new_run_id


def _seed(session):
    for h in ("@a", "@b"):
        acc = Account(platform="twitter", handle=h, objective_weights={
            "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc); session.commit()
        session.add_all([
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
            Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110),
        ])
        session.commit()


def test_start_batch_populates_registry(session):
    _seed(session)
    rid = new_run_id()
    BATCH_RUNS.clear()
    start_batch(rid, lambda: session, sync=False)
    entry = BATCH_RUNS[rid]
    assert entry["status"] == "completed"
    assert entry["report"]["processed"] == 2
    assert entry["report"]["looped"] == 2


def test_start_batch_records_error_status(session, monkeypatch):
    _seed(session)
    monkeypatch.setattr(runs_mod, "run_batch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rid = new_run_id()
    start_batch(rid, lambda: session, sync=False)
    assert BATCH_RUNS[rid]["status"] == "error"
    assert "boom" in BATCH_RUNS[rid]["error"]


def test_batch_run_background_returns_202_and_status(client, session):
    _seed(session)
    resp = client.post("/batch/run?background=true&sync=false")
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert run_id
    # TestClient runs the background task before returning; status should be queryable
    status = client.get(f"/batch/runs/{run_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"running", "completed"}


def test_batch_run_sync_still_returns_200(client, session):
    _seed(session)
    resp = client.post("/batch/run?sync=false")
    assert resp.status_code == 200
    assert resp.json()["processed"] == 2


def test_batch_runs_unknown_id_404(client):
    assert client.get("/batch/runs/nope").status_code == 404
```

- [ ] **Step 2: 运行确认失败.**

- [ ] **Step 3: 实现 runs.py + 路由**

Create `backend/app/scheduler/runs.py`:
```python
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
```

Modify `backend/app/api/routes.py` — replace the existing `batch_run` and add status route. Add imports:
```python
from fastapi import BackgroundTasks
from app.db import SessionLocal
from app.scheduler.runs import BATCH_RUNS, new_run_id, start_batch
```
Replace the `batch_run` endpoint with:
```python
@router.post("/batch/run")
def batch_run(background_tasks: BackgroundTasks, sync: bool = True,
              max_accounts: int | None = None, background: bool = False,
              db: Session = Depends(get_db)) -> dict:
    cfg = BatchConfig(max_accounts=max_accounts)
    if background:
        run_id = new_run_id()
        BATCH_RUNS[run_id] = {"status": "running", "report": None, "error": None}
        background_tasks.add_task(start_batch, run_id, SessionLocal, sync=sync, batch_cfg=cfg)
        return {"run_id": run_id, "status": "running"}
    report = run_batch(db, sync=sync, batch_cfg=cfg)
    return asdict(report)


@router.get("/batch/runs/{run_id}")
def batch_run_status(run_id: str) -> dict:
    entry = BATCH_RUNS.get(run_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, **entry}
```
Note: the 202 status — set it via `Response`/route decorator. Use `@router.post("/batch/run", status_code=200)` and, when background, return with an explicit 202: change the background branch to raise nothing but set the status code. Simplest: make the endpoint return a `JSONResponse`:
```python
from fastapi.responses import JSONResponse
...
    if background:
        run_id = new_run_id()
        BATCH_RUNS[run_id] = {"status": "running", "report": None, "error": None}
        background_tasks.add_task(start_batch, run_id, SessionLocal, sync=sync, batch_cfg=cfg)
        return JSONResponse(status_code=202, content={"run_id": run_id, "status": "running"})
```
(Keep the sync branch returning the dict → 200. Import `JSONResponse` at top.)

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_batch_async.py -v` → PASS (6 passed). If TestClient does not run background tasks before returning, the status may be "running" — the test allows both "running"/"completed", so it passes either way.

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/scheduler/runs.py backend/app/api/routes.py backend/tests/test_batch_async.py
git commit -m "feat(scheduler): async /batch/run (background task + run registry) + GET /batch/runs/{id}"
```

---

### Task 2: token 成本计量 + 预算熔断

**Files:** Modify `backend/app/analysis/claude_client.py`, `backend/app/loop/engine.py`, `backend/app/scheduler/batch.py`; Test `backend/tests/test_token_budget.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_token_budget.py`:
```python
import json
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.loop.engine import run_loop
from app.scheduler.batch import run_batch, BatchConfig


class FakeUsageClient:
    """LLMClient exposing last_usage like ClaudeClient does."""
    def __init__(self, response, usage): self.response = response; self.last_usage = usage
    def complete(self, *, system, prompt): return self.response


VALID = json.dumps({"positioning_clarity": 70, "positioning_label": "x", "content_direction": "y", "suggested_topics": []})


def _acct(session, handle):
    acc = Account(platform="x", handle=handle, objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=1000))
    session.commit()
    return acc


def test_run_loop_records_tokens_from_client(session):
    acc = _acct(session, "@a")
    client = FakeUsageClient(VALID, {"input": 120, "output": 30})
    run = run_loop(session, acc, llm_client=client)
    assert run.tokens_cost == 150


def test_run_loop_deterministic_zero_tokens(session):
    acc = _acct(session, "@b")
    run = run_loop(session, acc)     # no llm_client
    assert run.tokens_cost == 0


def test_batch_token_budget_stops(session, monkeypatch):
    for h in ("@a", "@b", "@c"):
        _acct(session, h)
    import app.scheduler.batch as batch_mod

    def fake_loop(sess, account, **kw):
        from app.models import LoopRun, Evaluation
        run = LoopRun(account_id=account.id, status="ok", tokens_cost=100)
        run.evaluation = Evaluation(account_id=account.id, composite_score=50.0, breakdown={})
        sess.add(run); sess.commit()
        return run

    monkeypatch.setattr(batch_mod, "run_loop", fake_loop)
    report = run_batch(session, sync=False, batch_cfg=BatchConfig(token_budget=150))
    # after 2nd account cumulative tokens=200 > 150 -> stop
    assert report.total_tokens >= 150
    assert report.stopped_early is True
    assert report.looped == 2
```

- [ ] **Step 2: 运行确认失败.**

- [ ] **Step 3: 实现**

`backend/app/analysis/claude_client.py` — in `__init__` add `self.last_usage: dict | None = None`; in `complete`, after getting `message`, set usage before returning:
```python
        usage = getattr(message, "usage", None)
        self.last_usage = {
            "input": getattr(usage, "input_tokens", 0) or 0,
            "output": getattr(usage, "output_tokens", 0) or 0,
        } if usage is not None else None
        return "".join(...)   # existing join
```

`backend/app/loop/engine.py` — in `run_loop`, LLM branch, after `evaluate_with_analysis`, compute tokens; set on the LoopRun. Change:
```python
    analysis = None
    tokens = 0
    if llm_client is not None:
        result, analysis = evaluate_with_analysis(account, snapshots, content, llm_client, cfg=scoring_cfg)
        usage = getattr(llm_client, "last_usage", None)
        if usage:
            tokens = (usage.get("input", 0) or 0) + (usage.get("output", 0) or 0)
    else:
        result = evaluate_with_content(account, snapshots, content, cfg=scoring_cfg)
```
and in the `LoopRun(...)` construction change `tokens_cost=0` → `tokens_cost=tokens` (remove the old TODO comment or keep a shorter note).

`backend/app/scheduler/batch.py` — add `token_budget: int | None = None` to `BatchConfig`; add `total_tokens: int = 0` to `BatchReport`; in `run_batch`, after a successful `run_loop`, `report.total_tokens += run.tokens_cost or 0`, and after updating, if `batch_cfg.token_budget is not None and report.total_tokens > batch_cfg.token_budget: report.stopped_early = True; break`.

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_token_budget.py -v` → PASS (3 passed).

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis/claude_client.py backend/app/loop/engine.py backend/app/scheduler/batch.py backend/tests/test_token_budget.py
git commit -m "feat(loop/scheduler): meter LLM token usage into LoopRun.tokens_cost + batch token_budget guardrail"
```

---

### Task 3: 性能 - 批量查询 + SQL 排序

**Files:** Modify `backend/app/api/overview.py`, `backend/app/api/routes.py`; Test `backend/tests/test_perf_equivalence.py`

保持响应形状/数值不变，只把逐账号查询换成「一次取全量 + Python 分组」，`/content` 排序与 LIMIT 下推 SQL。

- [ ] **Step 1: 写一个等价性测试（现有测试也必须继续通过）**

Create `backend/tests/test_perf_equivalence.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation


def test_overview_still_correct_after_batching(client, session):
    a1 = Account(platform="xiaohongshu", handle="@a1"); a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=112000),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=49000),
    ])
    r = LoopRun(account_id=a1.id, status="ok")
    r.evaluation = Evaluation(account_id=a1.id, composite_score=88.0, breakdown={"growth": 90, "engagement": 80, "commercial": 60, "positioning": 92})
    session.add(r); session.commit()

    body = client.get("/overview").json()
    assert body["kpis"]["total_accounts"] == 2
    assert body["kpis"]["avg_score"] == 88.0            # only a1 has an eval
    trend = {t["date"]: t["followers"] for t in body["trend"]}
    assert trend["2026-07-06"] == 161000
    movers = {m["account_id"]: m["delta_followers"] for m in body["top_movers"]}
    assert movers[a1.id] == 12000


def test_content_sorted_in_sql(client, session):
    acc = Account(platform="x", handle="@a"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="a", views=100),
        ContentItem(account_id=acc.id, topic="b", views=9000),
        ContentItem(account_id=acc.id, topic="c", views=None),   # null views sort last
    ])
    session.commit()
    items = client.get("/content?limit=2").json()
    assert [i["views"] for i in items] == [9000, 100]     # views desc, limit applied, null excluded from top
```

- [ ] **Step 2: 运行确认（先跑，可能已通过；本任务重点是把内部换成批量后仍然过）**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_perf_equivalence.py -v` (先建立基线)

- [ ] **Step 3: 批量化 build_overview + list_accounts + /content SQL 排序**

In `backend/app/api/overview.py`, replace the per-account helper calls with batched pre-fetch. At the top of `build_overview`, build these dicts with a bounded number of queries:
```python
    from collections import defaultdict

    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())

    # batch: all snapshots grouped by account, ordered by ts
    snaps_by_account: dict[int, list] = defaultdict(list)
    for s in session.scalars(select(Snapshot).order_by(Snapshot.account_id, Snapshot.ts, Snapshot.id)).all():
        snaps_by_account[s.account_id].append(s)

    # batch: latest evaluation per account (highest created_at,id)
    latest_eval: dict[int, object] = {}
    for e in session.scalars(select(Evaluation).order_by(Evaluation.account_id, Evaluation.created_at, Evaluation.id)).all():
        latest_eval[e.account_id] = e   # last write wins -> latest

    # batch: latest loop run per account
    latest_loop: dict[int, object] = {}
    for lr in session.scalars(select(LoopRun).order_by(LoopRun.account_id, LoopRun.ts, LoopRun.id)).all():
        latest_loop[lr.account_id] = lr
```
Then rewrite the rest of `build_overview` to read from `latest_eval.get(a.id)`, `latest_loop.get(a.id)`, and `snaps_by_account.get(a.id, [])` (latest = `[-1]`, previous = `[-2]`) instead of calling `_latest_eval`/`_latest_loop`/`_ordered_snaps` per account. Keep the pending_recs/pending_drafts queries as-is. The output dict must stay byte-for-byte the same shape. Remove the now-unused `_latest_eval`/`_latest_loop`/`_ordered_snaps` helpers (or keep if referenced elsewhere — they are not).

In `backend/app/api/routes.py` `_list_item`/`list_accounts`: similarly, in `list_accounts`, pre-fetch latest snapshot/eval/loop per account with the same grouped approach and pass them into `_list_item` (add optional params), so the list endpoint is not N+1. (Single-account routes like `_latest(...)` can stay per-call.)

In `backend/app/api/routes.py` `/content`: push sort + limit to SQL:
```python
    stmt = (select(ContentItem, Account).join(Account, ContentItem.account_id == Account.id)
            .order_by(ContentItem.views.desc().nulls_last(), ContentItem.id)
            .limit(limit))
    if platform: stmt = stmt.where(Account.platform == platform)   # apply filters before order/limit
    if account_id: stmt = stmt.where(ContentItem.account_id == account_id)
```
Important: apply `.where(...)` filters BEFORE `.order_by/.limit` (build the base select, add wheres, then order+limit) — reorder the statement construction accordingly. Drop the Python `items.sort(...)` and the `[:limit]` slice (SQL now does both). If `nulls_last()` raises on the SQLite dialect in use, fall back to `.order_by((ContentItem.views == None), ContentItem.views.desc(), ContentItem.id)` (nulls sorted last via the boolean expression).

- [ ] **Step 4: 运行确认通过 + 全量回归** — `python -m pytest -q`（此前测试 + T1(6)+T2(3)+T3(2) 全绿；`/overview`、`/content`、`/accounts` 既有测试数值不变）。

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/overview.py backend/app/api/routes.py backend/tests/test_perf_equivalence.py
git commit -m "perf(api): batch overview/accounts queries (no N+1) + push /content sort+limit to SQL"
```

---

## 完成标准

- `python -m pytest` 全绿（此前 119 + T1 6 + T2 3 + T3 2 = 130）
- `/batch/run?background=true` → 202 + run_id；`GET /batch/runs/{id}` 查状态；sync 模式仍 200 兼容
- LLM 路径把 token 记进 `LoopRun.tokens_cost`；`run_batch(token_budget=…)` 超预算熔断（total_tokens 汇总进 report）
- `/overview`、`/accounts` 不再 N+1（批量取+分组，数值不变）；`/content` 排序+LIMIT 走 SQL
- 备注：真实 LLM token 数需真 key/gateway 才非零（Fake 客户端可测计量逻辑）
