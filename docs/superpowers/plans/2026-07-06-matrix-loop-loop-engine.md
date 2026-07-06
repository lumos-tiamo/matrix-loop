# MatrixLoop 自我修正 Loop 引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现系统的心脏 - `run_loop(session, account)`：把评估+分析编排成一轮 LoopRun（诊断 + 纠偏建议 + 起草选题），并做验证（对比上一轮、标记已采纳建议见效/无效）与无进展护栏。人在环：草稿一律 pending，永不自动发。

**Architecture:** `app/loop/engine.py` 一个编排函数 `run_loop`。步骤：采集账号快照+内容 → 评估（无 llm_client 走确定性 `evaluate_with_content`，有则走 `evaluate_with_analysis` 拿 LLM 定位）→ 产出 diagnosis + Recommendations + Drafts → 验证（delta vs 上一轮，标记上一轮 adopted 建议 worked/failed）→ 无进展护栏（连续 N 轮复合分未提升 → status=no_progress）→ 持久化 LoopRun(+Evaluation+Recommendations+Drafts)。全部可用内存 session + 真实模型确定性测试；LLM 路径用 FakeLLMClient。

**Tech Stack:** Python 3.13（同一 venv），SQLAlchemy 2.0，pytest。无新依赖。

**依赖：** 地基 models、plan 2（`evaluate_with_content`、`hit_content`）、plan 3（`evaluate_with_analysis`、`AnalysisResult`）。

---

### Task 1: run_loop 核心（采集→评估→产出→持久化）

**Files:**
- Create: `backend/app/loop/__init__.py`
- Create: `backend/app/loop/engine.py`
- Test: `backend/tests/test_loop_engine_core.py`

- [ ] **Step 1: 写失败的核心测试**

Create `backend/tests/test_loop_engine_core.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun
from app.loop.engine import run_loop


def _seed(session, weights=None):
    acc = Account(platform="xiaohongshu", handle="@a1",
                  objective_weights=weights or {"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),  # +10% -> growth 100
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
        ContentItem(account_id=acc.id, views=1000, topic="beauty"),  # 爆文
    ])
    session.commit()
    return acc


def test_run_loop_persists_loop_run_with_evaluation(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    assert isinstance(run, LoopRun)
    assert run.id is not None
    assert run.evaluation is not None
    assert run.evaluation.composite_score == 100.0  # weights all on growth, +10% -> 100
    assert run.diagnosis  # non-empty
    assert session.query(LoopRun).count() == 1


def test_run_loop_produces_recommendations_and_hit_cadence(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    kinds = [r.kind for r in run.recommendations]
    assert "content_direction" in kinds
    assert "cadence" in kinds  # 有一条爆文 -> cadence 建议
    # 确定性路径不产出草稿（草稿来自 LLM suggested_topics）
    assert run.drafts == []


def test_run_loop_first_run_verify_is_baseline(session):
    acc = _seed(session)
    run = run_loop(session, acc)
    assert run.verify_result.get("baseline") is True
    assert run.status == "ok"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_core.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.loop'`

- [ ] **Step 3: 实现 engine.py（核心，无 verify/无护栏，先固定 verify_result 基线、status=ok）**

Create `backend/app/loop/__init__.py` (空文件).

Create `backend/app/loop/engine.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem, Draft, Evaluation, LoopRun, Recommendation, Snapshot
from app.evaluation.scoring import ScoringConfig, evaluate_with_content
from app.analysis.content import hit_content


@dataclass(frozen=True)
class LoopConfig:
    no_progress_limit: int = 3     # 连续 N 轮复合分未提升 -> status=no_progress
    min_improvement: float = 0.5   # 复合分提升需 > 该值才算"改善"


def _gather(session: Session, account_id: int):
    snaps = session.scalars(select(Snapshot).where(Snapshot.account_id == account_id)).all()
    content = session.scalars(select(ContentItem).where(ContentItem.account_id == account_id)).all()
    return list(snaps), list(content)


def _build_outputs(result, analysis, content_items):
    recs: list[Recommendation] = []
    drafts: list[Draft] = []
    if analysis is not None:
        diagnosis = (
            f"定位「{analysis.positioning_label}」，清晰度 {analysis.positioning_clarity:.0f}/100。"
            f"{analysis.content_direction}"
        )
        recs.append(Recommendation(kind="positioning", content=f"聚焦定位：{analysis.positioning_label}"))
        recs.append(Recommendation(kind="content_direction", content=analysis.content_direction))
        drafts.extend(Draft(kind="topic", content=t) for t in analysis.suggested_topics)
    else:
        pos = result.breakdown.get("positioning", 0.0)
        diagnosis = f"确定性评估：复合价值分 {result.composite_score:.0f}/100，定位清晰度代理 {pos:.0f}/100。"
        recs.append(Recommendation(
            kind="content_direction",
            content="定位偏散，建议收敛选题、聚焦单一垂类" if pos < 60 else "定位清晰，保持方向并提升优质内容产量",
        ))
    hits = hit_content(content_items)
    if hits:
        recs.append(Recommendation(
            kind="cadence",
            content=f"复制 {len(hits)} 条爆文的选题结构，提高高表现内容的产出频率",
        ))
    return diagnosis, recs, drafts


def run_loop(session: Session, account, *, llm_client=None, cfg: LoopConfig | None = None,
             scoring_cfg: ScoringConfig | None = None) -> LoopRun:
    cfg = cfg or LoopConfig()
    snapshots, content = _gather(session, account.id)

    analysis = None
    if llm_client is not None:
        from app.evaluation.scoring import evaluate_with_analysis
        result, analysis = evaluate_with_analysis(account, snapshots, content, llm_client, cfg=scoring_cfg)
    else:
        result = evaluate_with_content(account, snapshots, content, cfg=scoring_cfg)

    diagnosis, recs, drafts = _build_outputs(result, analysis, content)

    run = LoopRun(
        account_id=account.id,
        diagnosis=diagnosis,
        verify_result={"baseline": True, "improved": False, "delta": 0.0},
        tokens_cost=0,
        status="ok",
    )
    run.evaluation = Evaluation(
        account_id=account.id,
        composite_score=result.composite_score,
        breakdown=result.breakdown,
    )
    run.recommendations = recs
    run.drafts = drafts
    session.add(run)
    session.commit()
    return run
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_core.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/loop backend/tests/test_loop_engine_core.py
git commit -m "feat(loop): run_loop core - gather, evaluate, produce recommendations/drafts, persist LoopRun"
```

---

### Task 2: 验证步 + 标记上一轮建议

**Files:**
- Modify: `backend/app/loop/engine.py` (追加 `_previous_run`, `_verify`, `_mark_prev_recommendations`；改 run_loop 用它们)
- Test: `backend/tests/test_loop_engine_verify.py`

- [ ] **Step 1: 写失败的验证测试**

Create `backend/tests/test_loop_engine_verify.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.loop.engine import run_loop


def _acc(session):
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    return acc


def _add_snap(session, acc, day, followers):
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, day, tzinfo=timezone.utc), followers=followers))
    session.commit()


def test_second_run_improved_marks_prev_adopted_rec_worked(session):
    acc = _acc(session)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 105000)   # +5% -> growth 50 -> composite 50
    run1 = run_loop(session, acc)
    assert run1.verify_result["baseline"] is True
    # 用户采纳了 run1 的一条建议
    run1.recommendations[0].status = "adopted"
    session.commit()

    _add_snap(session, acc, 6, 110000)   # 100k->110k = +10% -> growth 100 -> composite 100
    run2 = run_loop(session, acc)
    assert run2.verify_result["baseline"] is False
    assert run2.verify_result["improved"] is True
    assert run2.verify_result["delta"] == 50.0
    assert run1.recommendations[0].status == "worked"


def test_second_run_not_improved_marks_prev_adopted_rec_failed(session):
    acc = _acc(session)
    _add_snap(session, acc, 1, 100000)
    _add_snap(session, acc, 2, 110000)   # +10% -> composite 100
    run1 = run_loop(session, acc)
    run1.recommendations[0].status = "adopted"
    session.commit()

    # 再加一个点让首末仍是 100k->110k（复合分不变）
    _add_snap(session, acc, 6, 110000)
    run2 = run_loop(session, acc)
    assert run2.verify_result["improved"] is False
    assert run2.verify_result["delta"] == 0.0
    assert run1.recommendations[0].status == "failed"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_verify.py -v`
Expected: FAIL - 断言失败（`verify_result["baseline"]` 恒为 True / prev 建议未被标记）

- [ ] **Step 3: 追加验证函数并接入 run_loop**

Append these functions to `backend/app/loop/engine.py`:
```python
def _previous_run(session: Session, account_id: int) -> LoopRun | None:
    stmt = (
        select(LoopRun)
        .where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
    )
    return session.scalars(stmt).first()


def _verify(prev: LoopRun | None, current_composite: float, cfg: LoopConfig) -> dict:
    if prev is None or prev.evaluation is None:
        return {"baseline": True, "improved": False, "delta": 0.0}
    delta = round(current_composite - prev.evaluation.composite_score, 2)
    return {"baseline": False, "improved": delta > cfg.min_improvement, "delta": delta}


def _mark_prev_recommendations(prev: LoopRun | None, verify: dict) -> None:
    if prev is None or verify.get("baseline"):
        return
    outcome = "worked" if verify["improved"] else "failed"
    for rec in prev.recommendations:
        if rec.status == "adopted":
            rec.status = outcome
```

Then in `run_loop`, REPLACE the hardcoded `verify_result={...}` construction. Specifically:
- After computing `result` (and before building the LoopRun), add:
```python
    prev = _previous_run(session, account.id)
    verify = _verify(prev, result.composite_score, cfg)
    _mark_prev_recommendations(prev, verify)
```
- Change the `LoopRun(...)` construction to use `verify_result=verify` instead of the hardcoded dict:
```python
    run = LoopRun(
        account_id=account.id,
        diagnosis=diagnosis,
        verify_result=verify,
        tokens_cost=0,
        status="ok",
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_verify.py tests/test_loop_engine_core.py -v`
Expected: PASS (5 passed — 含 Task 1 的 3 个仍绿)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/loop/engine.py backend/tests/test_loop_engine_verify.py
git commit -m "feat(loop): verify step - delta vs previous run, mark adopted recommendations worked/failed"
```

---

### Task 3: 无进展护栏

**Files:**
- Modify: `backend/app/loop/engine.py` (追加 `_status`；run_loop 用它)
- Test: `backend/tests/test_loop_engine_guardrail.py`

- [ ] **Step 1: 写失败的护栏测试**

Create `backend/tests/test_loop_engine_guardrail.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.loop.engine import run_loop, LoopConfig


def test_flat_runs_trigger_no_progress(session):
    acc = Account(platform="x", handle="@a", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    # 固定两点 100k->110k，复合分恒为 100，不随重复 run 变化
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()

    cfg = LoopConfig(no_progress_limit=3, min_improvement=0.5)
    statuses = [run_loop(session, acc, cfg=cfg).status for _ in range(4)]
    # 前 3 轮历史不足，ok；第 4 轮已有 3 条持平历史 -> no_progress
    assert statuses[:3] == ["ok", "ok", "ok"]
    assert statuses[3] == "no_progress"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_guardrail.py -v`
Expected: FAIL - 第 4 轮 status 仍为 "ok"

- [ ] **Step 3: 追加 _status 并接入 run_loop**

Append to `backend/app/loop/engine.py`:
```python
def _status(session: Session, account_id: int, current_composite: float, cfg: LoopConfig) -> str:
    stmt = (
        select(Evaluation)
        .join(LoopRun, Evaluation.loop_run_id == LoopRun.id)
        .where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
        .limit(cfg.no_progress_limit)
    )
    prior = [e.composite_score for e in session.scalars(stmt)]
    if len(prior) >= cfg.no_progress_limit:
        oldest_in_window = prior[cfg.no_progress_limit - 1]
        if current_composite - oldest_in_window <= cfg.min_improvement:
            return "no_progress"
    return "ok"
```

Then in `run_loop`, compute status before building the LoopRun (after `verify`/`_mark_prev_recommendations`):
```python
    status = _status(session, account.id, result.composite_score, cfg)
```
and change the LoopRun construction `status="ok"` to `status=status`.

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_guardrail.py tests/test_loop_engine_verify.py tests/test_loop_engine_core.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/loop/engine.py backend/tests/test_loop_engine_guardrail.py
git commit -m "feat(loop): no-progress guardrail - flat composite over N runs -> status=no_progress"
```

---

### Task 4: LLM 路径（analysis 增强诊断/建议/草稿）

**Files:**
- Test: `backend/tests/test_loop_engine_llm.py`
- （engine.py 的 LLM 分支在 Task 1 已实现；本任务补测试并验证串通）

- [ ] **Step 1: 写失败的 LLM 路径测试**

Create `backend/tests/test_loop_engine_llm.py`:
```python
import json
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem
from app.loop.engine import run_loop


class FakeLLMClient:
    def __init__(self, response): self.response = response
    def complete(self, *, system, prompt): return self.response


def test_run_loop_llm_path_enriches_outputs(session):
    acc = Account(platform="xiaohongshu", handle="@a1", objective_weights={
        "growth": 0.0, "engagement": 0.0, "commercial": 0.0, "positioning": 1.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=100000),
        ContentItem(account_id=acc.id, views=100, topic="beauty"),
    ])
    session.commit()

    client = FakeLLMClient(json.dumps({
        "positioning_clarity": 72,
        "positioning_label": "平价美妆测评",
        "content_direction": "聚焦百元内产品横评",
        "suggested_topics": ["5款百元粉底横评", "学生党护肤清单"],
    }))

    run = run_loop(session, acc, llm_client=client)

    # positioning 权重 1.0 -> 复合分 == LLM 清晰度 72
    assert run.evaluation.composite_score == 72.0
    assert "平价美妆测评" in run.diagnosis
    kinds = {r.kind for r in run.recommendations}
    assert {"positioning", "content_direction"} <= kinds
    # suggested_topics -> 两条草稿
    topics = sorted(d.content for d in run.drafts if d.kind == "topic")
    assert topics == ["5款百元粉底横评", "学生党护肤清单"]
```

- [ ] **Step 2: 运行确认（可能已通过，因为 Task 1 实现了 LLM 分支）**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_loop_engine_llm.py -v`
Expected: PASS (1 passed)。若失败，检查 Task 1 的 LLM 分支与 `_build_outputs` 的 analysis 分支是否与本测试断言一致，修正后再跑。

- [ ] **Step 3: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（此前 53 + 本计划 7 = 60 passed）

- [ ] **Step 4: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/tests/test_loop_engine_llm.py
git commit -m "test(loop): cover LLM path - analysis enriches diagnosis, recommendations, drafts"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（此前 53 + 本计划 7 = 60）
- `run_loop(session, account)` 跑一轮并持久化 LoopRun（含 Evaluation、Recommendations、Drafts、diagnosis、verify_result、status）
- 无 llm_client 走确定性路径；有 llm_client 用 LLM 定位清晰度 + 起草选题
- 验证步对比上一轮、标记上一轮 adopted 建议 worked/failed
- 无进展护栏：连续 N 轮复合分未提升 → status=no_progress
- 人在环：Drafts/Recommendations 一律 pending，Loop 不自动发布
- 备注（后续计划）：真实 token 成本上限需 LLMClient 暴露 usage（调度计划 8 再补）；tokens_cost 暂记 0
