# Autonomous Orchestrator + Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the flywheel self-spinning after hours: a scheduled cycle advances each account through the pipeline; **autopilot** accounts auto-advance the human gates (adopt topic → script → adopt → video → approve → publish) under guardrails; non-autopilot accounts stop at the review queue. Every auto-action is audited; a global kill-switch pauses everything; a `/flywheel` API exposes live per-step + per-account state for the UI. So the operator only connects accounts once and watches exceptions.

**Architecture:** A per-account state machine `advance_account` orchestrates the existing pieces (`sync_account`, `run_loop`, `generate_script`, `generate_video`, `create_dispatch`, `refresh_published_analytics`). It degrades gracefully — if a dependency (LLM / real video provider / AiToEarn) is unavailable it stops at that step and logs, never publishing junk. `run_autopilot_cycle` iterates accounts with per-account isolation, a consecutive-error circuit breaker, and a global-pause check. APScheduler runs the cycle + analytics refresh on an interval. Guardrails reuse the video usage governor + compliance stance; auto-publish is gated on `Account.autopilot` (per-account human opt-in) + a real (non-fake) approved video + configured AiToEarn.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, APScheduler, pytest. Backend Python: `backend/.venv/bin/python`; run pytest from `backend/`.

**Scope:** Per-account orchestration (steps ②定调→⑨改进), scheduled cycle, autopilot toggle, kill-switch, audit, `/flywheel` state API. **Deferred:** ①爬取爆款 trend module (separate `trends` plan, uses agent-reach); the flywheel React UI (separate frontend plan, consumes `/flywheel`). Real auto-publish still needs Seedance (real video) + AiToEarn running — the engine advances as far as deps allow and is fully fake-tested offline.

Preconditions: on `main`, clean, `git checkout -b feat/orchestrator`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 237 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `backend/app/models.py` (modify) — `Account.autopilot`; new `AppState` (key/value), `FlywheelEvent` (audit).
- `backend/app/orchestrator/__init__.py` (create, empty), `backend/app/orchestrator/engine.py` (create) — `OrchestratorConfig`, `advance_account`, `run_autopilot_cycle`, `STEPS`.
- `backend/app/orchestrator/state.py` (create) — `AppState` helpers (`is_paused`, `set_paused`) + `flywheel_state(session)` aggregation.
- `backend/app/scheduler/runner.py` (modify) — schedule the autopilot cycle + analytics refresh.
- `backend/app/config.py` (modify) — orchestrator cadence + guardrail defaults.
- `backend/app/api/routes.py` (modify) — autopilot toggle, `/flywheel/pause|resume|status`, `GET /flywheel`.
- `backend/app/api/schemas.py` (modify) — `SetAutopilot`.
- Tests: `test_models_orchestrator.py`, `test_orchestrator_advance.py`, `test_orchestrator_cycle.py`, `test_flywheel_state.py`, `test_api_flywheel.py` (create).

---

### Task 1: Models — autopilot flag, AppState, FlywheelEvent

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models_orchestrator.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, AppState, FlywheelEvent


def test_account_autopilot_default_false(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    assert a.autopilot is False
    a.autopilot = True; session.commit()
    assert session.get(Account, a.id).autopilot is True


def test_appstate_key_value(session):
    session.add(AppState(key="flywheel_paused", value="1")); session.commit()
    row = session.get(AppState, "flywheel_paused")
    assert row.value == "1"


def test_flywheel_event_persist(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    ev = FlywheelEvent(account_id=a.id, cycle_id="c1", step="script", status="ok", detail="generated")
    session.add(ev); session.commit()
    got = session.query(FlywheelEvent).one()
    assert got.step == "script" and got.status == "ok" and got.account_id == a.id
```

- [ ] **Step 2: Run — expect FAIL.** `./.venv/bin/python -m pytest tests/test_models_orchestrator.py -q`

- [ ] **Step 3: Implement**

In `backend/app/models.py`, add to `class Account` (after `external_source`):

```python
    autopilot: Mapped[bool] = mapped_column(default=False)
```

At end of file add:

```python
class AppState(Base):
    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)


class FlywheelEvent(Base):
    __tablename__ = "flywheel_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    cycle_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    step: Mapped[str] = mapped_column(String(16))                 # sync|evaluate|topic|script|video|publish|track
    status: Mapped[str] = mapped_column(String(12))               # ok|skipped|blocked|error
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
```

(`Boolean` isn't needed — `Mapped[bool]` maps to Boolean automatically. `Integer`, `String`, `DateTime`, `ForeignKey`, `_utcnow` already imported.)

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_orchestrator.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(models): Account.autopilot + AppState + FlywheelEvent (audit)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: recreate dev DB after this plan.

---

### Task 2: Config + AppState/pause helpers

**Files:** Modify `backend/app/config.py`; Create `backend/app/orchestrator/__init__.py` (empty) + `backend/app/orchestrator/state.py`; Test `backend/tests/test_flywheel_state.py` (create, pause part)

- [ ] **Step 1: Write the failing test**

```python
from app.orchestrator.state import is_paused, set_paused


def test_pause_roundtrip(session):
    assert is_paused(session) is False        # default: not paused
    set_paused(session, True)
    assert is_paused(session) is True
    set_paused(session, False)
    assert is_paused(session) is False
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Config additions** — in `backend/app/config.py` `Settings`, add:

```python
    orchestrator_interval_minutes: int = 180
    orchestrator_allow_fake_publish: bool = False
```

- [ ] **Step 4: Implement `backend/app/orchestrator/__init__.py`** (empty) and `backend/app/orchestrator/state.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AppState

_PAUSE_KEY = "flywheel_paused"


def is_paused(session: Session) -> bool:
    row = session.get(AppState, _PAUSE_KEY)
    return bool(row and row.value == "1")


def set_paused(session: Session, paused: bool) -> None:
    row = session.get(AppState, _PAUSE_KEY)
    if row is None:
        row = AppState(key=_PAUSE_KEY)
        session.add(row)
    row.value = "1" if paused else "0"
    session.commit()
```

- [ ] **Step 5: Run — expect PASS.** `./.venv/bin/python -m pytest tests/test_flywheel_state.py -q`

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/config.py backend/app/orchestrator/__init__.py backend/app/orchestrator/state.py backend/tests/test_flywheel_state.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(orchestrator): config + AppState pause helpers\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: `advance_account` state machine

**Files:** Create `backend/app/orchestrator/engine.py`; Test `backend/tests/test_orchestrator_advance.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from app.models import Account, ContentItem, Draft, FlywheelEvent, LoopRun, Snapshot, VideoAsset
from app.orchestrator.engine import advance_account, OrchestratorConfig


class _LLM:
    def complete(self, *, system, prompt): return "Hook: crypto script ..."
    last_usage = {"input": 1, "output": 1}


class _Video:
    name = "seedance"
    def generate(self, *, script, brief, params):
        from app.video.base import VideoResult
        return VideoResult(media_url="https://cdn/x.mp4", duration=5, cost=1, provider="seedance",
                           dedup_key="d", metadata={})


class _Fake:
    name = "fake"
    def generate(self, *, script, brief, params):
        from app.video.base import VideoResult
        return VideoResult(media_url="https://fake.local/x.mp4", duration=5, cost=1, provider="fake",
                           dedup_key="d", metadata={})


class _AiToEarn:
    def publish_flow(self, payload):
        return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}
    def flow_status(self, fid): return {"tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}


def _acct(session, handle="@x", autopilot=False, external_ref="ae_1"):
    a = Account(platform="tiktok", handle=handle, autopilot=autopilot, external_ref=external_ref,
                objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(a); session.commit()
    session.add_all([
        Snapshot(account_id=a.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        ContentItem(account_id=a.id, topic="airdrop", views=5000),
    ]); session.commit()
    return a


def test_non_autopilot_stops_at_review_queue(session):
    a = _acct(session, autopilot=False)
    rep = advance_account(session, a, llm=_LLM(), video=_Fake(), aitoearn=None, sync=False)
    assert rep["reached_step"] in ("evaluate", "topic")   # produced drafts, did NOT auto-advance
    # no video asset, no dispatch created
    assert session.query(VideoAsset).count() == 0
    # a topic draft exists (from the loop) but is NOT auto-adopted
    topics = session.query(Draft).filter_by(kind="topic").all()
    assert topics and all(d.review_status != "adopted" for d in topics)


def test_autopilot_advances_through_publish_with_real_video(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Video(), aitoearn=_AiToEarn(),
                          sync=False, cfg=OrchestratorConfig())
    assert rep["reached_step"] == "publish"
    # a script draft was auto-adopted, a video generated + approved, a dispatch created
    assert session.query(Draft).filter_by(kind="script").filter(Draft.review_status == "adopted").count() >= 1
    v = session.query(VideoAsset).one()
    assert v.review_status == "approved" and v.provider == "seedance"
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 1
    # audit trail recorded steps
    steps = [e.step for e in session.query(FlywheelEvent).order_by(FlywheelEvent.id).all()]
    assert "script" in steps and "video" in steps and "publish" in steps


def test_autopilot_does_not_publish_fake_video(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Fake(), aitoearn=_AiToEarn(),
                          sync=False, cfg=OrchestratorConfig(allow_fake_publish=False))
    assert rep["reached_step"] == "video"           # produced fake video, refused to publish it
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 0
    blocked = [e for e in session.query(FlywheelEvent).all() if e.status == "blocked"]
    assert any("fake" in (e.detail or "").lower() or e.step == "publish" for e in blocked)


def test_autopilot_blocks_publish_without_aitoearn(session):
    a = _acct(session, autopilot=True, external_ref="ae_1")
    rep = advance_account(session, a, llm=_LLM(), video=_Video(), aitoearn=None, sync=False)
    assert rep["reached_step"] == "approve"          # video approved but no AiToEarn -> can't publish
    from app.models import PublishDispatch
    assert session.query(PublishDispatch).count() == 0


def test_autopilot_without_llm_stops_at_topic(session):
    a = _acct(session, autopilot=True)
    rep = advance_account(session, a, llm=None, video=_Video(), aitoearn=_AiToEarn(), sync=False)
    assert rep["reached_step"] in ("evaluate", "topic")   # no LLM -> no script -> no video/publish
    assert session.query(VideoAsset).count() == 0
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `backend/app/orchestrator/engine.py`**

```python
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.performance import content_performance, performance_prompt_block
from app.analysis.script import generate_script
from app.connectors.base import ManualOnlyError
from app.connectors.sync import sync_account
from app.loop.engine import run_loop
from app.models import ChannelBrief, Draft, LoopRun, VideoAsset
from app.orchestrator.state import is_paused
from app.publish.dispatch import PublishNotReady, create_dispatch
from app.video.base import NearDuplicateScript, VideoQuotaExceeded
from app.video.governor import generate_video

logger = logging.getLogger(__name__)

STEPS = ["sync", "evaluate", "topic", "script", "video", "approve", "publish", "track"]


@dataclass(frozen=True)
class OrchestratorConfig:
    allow_fake_publish: bool = False           # never publish a fake-provider video as real
    stop_after_consecutive_errors: int = 5


def _event(session, account_id, cycle_id, step, status, detail=""):
    from app.models import FlywheelEvent
    session.add(FlywheelEvent(account_id=account_id, cycle_id=cycle_id, step=step,
                              status=status, detail=(detail or "")[:400]))


def advance_account(session: Session, account, *, llm=None, video=None, aitoearn=None,
                    sync: bool = True, cfg: OrchestratorConfig | None = None,
                    cycle_id: str | None = None) -> dict:
    """Advance one account through the flywheel. Autopilot accounts auto-advance the human gates
    under guardrails; others stop after producing topic drafts. Degrades gracefully when a
    dependency is missing. Returns {account_id, reached_step, actions, errors}."""
    cfg = cfg or OrchestratorConfig()
    actions: list[str] = []
    reached = "sync"

    def mark(step, status, detail=""):
        nonlocal reached
        _event(session, account.id, cycle_id, step, status, detail)
        if status == "ok":
            reached = step
        actions.append(f"{step}:{status}")

    # ① sync (best-effort)
    if sync:
        try:
            sync_account(session, account)
            mark("sync", "ok")
        except ManualOnlyError:
            mark("sync", "skipped", "manual-only platform / not mapped")
        except Exception as exc:  # noqa: BLE001
            mark("sync", "error", str(exc))

    # ② evaluate + topics (run_loop)
    try:
        run = run_loop(session, account, llm_client=llm)
        mark("evaluate", "ok", f"score={run.evaluation.composite_score if run.evaluation else '?'}")
    except Exception as exc:  # noqa: BLE001
        mark("evaluate", "error", str(exc))
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}

    # newest topic draft from this run
    topic = next((d for d in reversed(run.drafts) if d.kind == "topic"), None)
    if topic is not None:
        mark("topic", "ok", topic.content[:60])

    # non-autopilot: stop here (review queue)
    if not account.autopilot:
        mark("topic", "skipped", "not autopilot: queued for human review")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}

    # ---- autopilot auto-advance ----
    if topic is None:
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    topic.review_status = "adopted"

    # ③ script
    if llm is None:
        mark("script", "blocked", "no LLM configured")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    brief = session.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account.id))
    perf = performance_prompt_block(content_performance(session, account.id))
    try:
        text = generate_script(topic.content, brief, llm, performance=perf or None)
    except Exception as exc:  # noqa: BLE001
        mark("script", "error", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}
    script = Draft(loop_run_id=topic.loop_run_id, kind="script", content=text, review_status="adopted")
    session.add(script); session.commit()
    mark("script", "ok")

    # ④ video (governed)
    if video is None:
        mark("video", "blocked", "no video provider"); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    try:
        asset = generate_video(session, account, script, provider=video)
    except (VideoQuotaExceeded, NearDuplicateScript) as exc:
        mark("video", "blocked", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    except Exception as exc:  # noqa: BLE001
        mark("video", "error", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}
    mark("video", "ok", asset.provider)

    # guardrail: do not publish a fake video as real
    if asset.provider == "fake" and not cfg.allow_fake_publish:
        mark("publish", "blocked", "fake video not published (allow_fake_publish=False)")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}

    # ⑤ approve (autopilot)
    asset.review_status = "approved"; session.commit()
    mark("approve", "ok")

    # ⑥ publish
    if aitoearn is None or not account.external_ref:
        mark("publish", "blocked", "AiToEarn not configured or account not mapped")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    try:
        create_dispatch(session, account, asset, client=aitoearn, caption=(topic.content or "")[:120])
        mark("publish", "ok")
    except PublishNotReady as exc:
        mark("publish", "blocked", str(exc))
    except Exception as exc:  # noqa: BLE001
        mark("publish", "error", str(exc))

    session.commit()
    return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
```

- [ ] **Step 4: Run — expect PASS** (`tests/test_orchestrator_advance.py`).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/orchestrator/engine.py backend/tests/test_orchestrator_advance.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(orchestrator): advance_account flywheel state machine (autopilot + guardrails + audit)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: `run_autopilot_cycle`

**Files:** Modify `backend/app/orchestrator/engine.py`; Test `backend/tests/test_orchestrator_cycle.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.orchestrator.engine import run_autopilot_cycle, OrchestratorConfig
from app.orchestrator.state import set_paused
from app.orchestrator.test_helpers_advance import _LLM, _Video, _AiToEarn  # if you factor helpers; else inline


class _LLM2:
    def complete(self, *, system, prompt): return "script"
    last_usage = {"input": 1, "output": 1}


def _acct(session, handle, autopilot):
    a = Account(platform="tiktok", handle=handle, autopilot=autopilot, external_ref="ae",
                objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(a); session.commit()
    session.add(Snapshot(account_id=a.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100))
    session.commit()
    return a


def test_cycle_processes_all_accounts(session):
    _acct(session, "@a", True); _acct(session, "@b", False)
    rep = run_autopilot_cycle(session, llm=_LLM2(), video=None, aitoearn=None, sync=False)
    assert rep["processed"] == 2
    assert rep["paused"] is False


def test_cycle_respects_global_pause(session):
    _acct(session, "@a", True)
    set_paused(session, True)
    rep = run_autopilot_cycle(session, llm=_LLM2(), video=None, aitoearn=None, sync=False)
    assert rep["paused"] is True and rep["processed"] == 0
```

(Inline the `_LLM2` etc. helpers; do not import from a non-existent module — the import line above is illustrative, replace with inline fakes.)

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Append to `backend/app/orchestrator/engine.py`**

```python
def run_autopilot_cycle(session: Session, *, llm=None, video=None, aitoearn=None,
                        sync: bool = True, cfg: OrchestratorConfig | None = None) -> dict:
    """One scheduled pass: advance every account (autopilot ones through publish; others to review).
    Honors the global pause, isolates per-account failures, and trips a consecutive-error breaker."""
    cfg = cfg or OrchestratorConfig()
    if is_paused(session):
        return {"paused": True, "processed": 0, "results": [], "errors": []}
    import uuid
    cycle_id = uuid.uuid4().hex[:12]
    accounts = list(session.scalars(select(__import__("app.models", fromlist=["Account"]).Account)).all())
    processed = 0
    results = []
    errors = []
    consecutive = 0
    for acc in accounts:
        try:
            rep = advance_account(session, acc, llm=llm, video=video, aitoearn=aitoearn,
                                  sync=sync, cfg=cfg, cycle_id=cycle_id)
            results.append(rep)
            processed += 1
            consecutive = 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("cycle: account %s failed: %s", acc.id, exc)
            errors.append({"account_id": acc.id, "error": str(exc)})
            consecutive += 1
            if consecutive >= cfg.stop_after_consecutive_errors:
                break
    return {"paused": False, "cycle_id": cycle_id, "processed": processed,
            "results": results, "errors": errors}
```

Replace the awkward `__import__` with a clean top-level `from app.models import Account` import at the top of the file.

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/orchestrator/engine.py backend/tests/test_orchestrator_cycle.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(orchestrator): run_autopilot_cycle (pause-aware, isolated, circuit breaker)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Scheduler wiring

**Files:** Modify `backend/app/scheduler/runner.py`; Test `backend/tests/test_scheduler_runner.py` (extend if present, else create)

- [ ] **Step 1: Write the failing test**

```python
def test_build_scheduler_registers_autopilot_and_analytics_jobs():
    from app.scheduler.runner import build_scheduler
    sched = build_scheduler(lambda: None, interval_minutes=30)
    ids = {j.id for j in sched.get_jobs()}
    assert "matrixloop-autopilot" in ids
    # does not auto-start
    assert not sched.running
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Extend `backend/app/scheduler/runner.py`** — add a job that runs the autopilot cycle + analytics refresh, resolving live deps. Add:

```python
def _run_autopilot(session_factory: Callable) -> None:
    from app.orchestrator.engine import run_autopilot_cycle
    from app.analysis.factory import resolve_llm_client
    from app.video.factory import resolve_video_provider
    from app.config import settings as cfg
    session = session_factory()
    try:
        aitoearn = None
        if cfg.aitoearn_base_url and cfg.aitoearn_api_key:
            from app.connectors.aitoearn_client import AiToEarnClient
            aitoearn = AiToEarnClient(cfg.aitoearn_base_url, cfg.aitoearn_api_key)
        rep = run_autopilot_cycle(session, llm=resolve_llm_client(),
                                  video=resolve_video_provider(), aitoearn=aitoearn, sync=True)
        logger.info("autopilot cycle: paused=%s processed=%s errors=%s",
                    rep.get("paused"), rep.get("processed"), len(rep.get("errors", [])))
        if aitoearn is not None:
            from app.publish.analytics import refresh_published_analytics
            refresh_published_analytics(session, client=aitoearn)
    except Exception:
        logger.exception("autopilot cycle failed")
    finally:
        session.close()
```

And in `build_scheduler`, add (keep the existing batch job or replace it — register the autopilot job with id `matrixloop-autopilot`):

```python
    from app.config import settings as _s
    interval = interval_minutes if interval_minutes is not None else _s.orchestrator_interval_minutes
    scheduler.add_job(_run_autopilot, "interval", minutes=interval,
                      args=[session_factory], id="matrixloop-autopilot", replace_existing=True)
```

(Keep the function not auto-starting. The existing `matrixloop-batch` job may remain or be removed — removing avoids double-looping; if you keep it, that's fine, but prefer replacing the batch job with the autopilot job to avoid redundant loops. Ensure the existing `test_scheduler_runner` tests still pass — adjust them if they asserted the old job id.)

- [ ] **Step 4: Run — expect PASS** (`tests/test_scheduler_runner.py`).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/scheduler/runner.py backend/tests/test_scheduler_runner.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(scheduler): schedule autopilot cycle + analytics refresh\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: APIs — autopilot toggle, kill-switch, `/flywheel` state

**Files:** Modify `backend/app/orchestrator/state.py` (add `flywheel_state`); Modify `backend/app/api/schemas.py` (`SetAutopilot`); Modify `backend/app/api/routes.py`; Test `backend/tests/test_api_flywheel.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, Draft, LoopRun, VideoAsset, PublishDispatch, FlywheelEvent


def _seed(session):
    a = Account(platform="tiktok", handle="@x"); session.add(a); session.commit()
    return a


def test_autopilot_toggle(client, session):
    a = _seed(session)
    r = client.post(f"/accounts/{a.id}/autopilot", json={"enabled": True})
    assert r.status_code == 200 and r.json()["autopilot"] is True
    session.refresh(a); assert a.autopilot is True


def test_pause_resume_status(client, session):
    assert client.get("/flywheel/status").json()["paused"] is False
    assert client.post("/flywheel/pause").status_code == 200
    assert client.get("/flywheel/status").json()["paused"] is True
    client.post("/flywheel/resume")
    assert client.get("/flywheel/status").json()["paused"] is False


def test_flywheel_state_shape(client, session):
    a = _seed(session); a.autopilot = True; session.commit()
    session.add(FlywheelEvent(account_id=a.id, step="script", status="ok", detail="x")); session.commit()
    body = client.get("/flywheel").json()
    assert "steps" in body and len(body["steps"]) == 9         # the 9 flywheel steps
    assert "accounts" in body and "events" in body and "paused" in body
    assert any(s["key"] == "video" for s in body["steps"])
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Add `flywheel_state` to `backend/app/orchestrator/state.py`**

```python
def flywheel_state(session: Session, *, event_limit: int = 20) -> dict:
    """Aggregate live per-step counts + per-account autopilot state + recent audit events for the UI."""
    from app.models import (Account, ContentItem, Draft, FlywheelEvent, PublishDispatch, VideoAsset)
    from sqlalchemy import func, select as _select

    def _count(stmt) -> int:
        return int(session.scalar(stmt) or 0)

    topics = _count(_select(func.count(Draft.id)).where(Draft.kind == "topic"))
    scripts = _count(_select(func.count(Draft.id)).where(Draft.kind == "script"))
    videos = _count(_select(func.count(VideoAsset.id)))
    pending_vid = _count(_select(func.count(VideoAsset.id)).where(VideoAsset.review_status == "pending"))
    dispatches = _count(_select(func.count(PublishDispatch.id)))
    published = _count(_select(func.count(PublishDispatch.id)).where(PublishDispatch.status == "published"))
    tracked = _count(_select(func.count(ContentItem.id)).where(ContentItem.platform_post_id.is_not(None)))
    accounts_total = _count(_select(func.count(Account.id)))
    autopilot_n = _count(_select(func.count(Account.id)).where(Account.autopilot.is_(True)))

    steps = [
        {"key": "crawl",    "label": "爬爆款",   "count": 0,           "status": "pending"},
        {"key": "brief",    "label": "定调",     "count": accounts_total, "status": "ok"},
        {"key": "script",   "label": "脚本",     "count": scripts,     "status": "ok" if scripts else "pending"},
        {"key": "video",    "label": "视频",     "count": videos,      "status": "ok" if videos else "pending"},
        {"key": "publish",  "label": "发布",     "count": dispatches,  "status": "ok" if dispatches else "pending"},
        {"key": "track",    "label": "追踪流量", "count": tracked,     "status": "ok" if tracked else "pending"},
        {"key": "retro",    "label": "复盘",     "count": published,   "status": "ok" if published else "pending"},
        {"key": "evaluate", "label": "账号评估", "count": accounts_total, "status": "ok"},
        {"key": "improve",  "label": "改进建议", "count": topics,      "status": "ok" if topics else "pending"},
    ]
    accts = [
        {"id": a.id, "handle": a.handle, "platform": a.platform, "autopilot": a.autopilot}
        for a in session.scalars(_select(Account).order_by(Account.id)).all()
    ]
    evs = session.scalars(
        _select(FlywheelEvent).order_by(FlywheelEvent.id.desc()).limit(event_limit)
    ).all()
    events = [{"account_id": e.account_id, "step": e.step, "status": e.status,
               "detail": e.detail, "ts": e.ts.isoformat() if e.ts else None} for e in evs]
    return {"paused": is_paused(session), "autopilot_accounts": autopilot_n,
            "steps": steps, "accounts": accts, "events": events, "pending_review": pending_vid}
```

- [ ] **Step 4: Add schema** — in `backend/app/api/schemas.py`:

```python
class SetAutopilot(BaseModel):
    enabled: bool
```

- [ ] **Step 5: Add routes** — in `backend/app/api/routes.py` (import at top: `from app.orchestrator.state import is_paused, set_paused, flywheel_state`; `FlywheelEvent` not needed in routes):

```python
@router.post("/accounts/{account_id}/autopilot")
def set_autopilot(account_id: int, payload: schemas.SetAutopilot, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc.autopilot = payload.enabled
    db.commit()
    return {"account_id": account_id, "autopilot": acc.autopilot}


@router.get("/flywheel/status")
def flywheel_status(db: Session = Depends(get_db)) -> dict:
    return {"paused": is_paused(db)}


@router.post("/flywheel/pause")
def flywheel_pause(db: Session = Depends(get_db)) -> dict:
    set_paused(db, True)
    return {"paused": True}


@router.post("/flywheel/resume")
def flywheel_resume(db: Session = Depends(get_db)) -> dict:
    set_paused(db, False)
    return {"paused": False}


@router.get("/flywheel")
def flywheel(db: Session = Depends(get_db)) -> dict:
    return flywheel_state(db)
```

Route ordering: register `/flywheel/status|pause|resume` and `/flywheel` — all static `/flywheel*` prefixes, and `/accounts/{id}/autopilot` is 3-segment. No collisions.

- [ ] **Step 6: Run — expect PASS** (`tests/test_api_flywheel.py`).

- [ ] **Step 7: Full suite regression** — `cd backend && ./.venv/bin/python -m pytest -q` — all pass (237 baseline + new).

- [ ] **Step 8: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/orchestrator/state.py backend/app/api/schemas.py backend/app/api/routes.py backend/tests/test_api_flywheel.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(api): autopilot toggle + flywheel pause/resume/status + GET /flywheel state\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Final code review over the branch diff.
- Recreate dev DB (new columns/tables): `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- `superpowers:finishing-a-development-branch` → merge to `main` (`--no-ff`).
- Update `docs/DELIVERY.md`: orchestrator + autopilot + kill-switch done; `GET /flywheel` is the UI data source.

## Deferred follow-ups (documented)

- ①爬取爆款 trend module (agent-reach research → trending crypto topics → seed topic generation) — separate plan.
- Flywheel React UI consuming `GET /flywheel` — separate frontend plan (mockup pending sign-off).
- Actually starting the scheduler at app startup (a lifespan hook) — deliberately left manual/off by default so it never auto-runs unexpectedly; wire to a startup flag when the operator wants unattended mode.

## Self-review

- **Coverage:** autopilot flag + audit + pause state (T1-2), per-account state machine with autopilot gating + guardrails + graceful degradation (T3), pause-aware isolated cycle with circuit breaker (T4), scheduled cycle + analytics (T5), toggle + kill-switch + `/flywheel` state API (T6).
- **Human-in-loop reframed correctly:** auto-publish only for `autopilot=True` accounts (per-account human opt-in), only a real (non-fake) approved video, only with AiToEarn configured — else it stops + audits. Global kill-switch + audit trail for trust.
- **Type consistency:** `advance_account(session, account, *, llm, video, aitoearn, sync, cfg, cycle_id)` and `run_autopilot_cycle(...)` signatures match call sites (tests, scheduler); `flywheel_state` returns the shape the UI + tests assert; `OrchestratorConfig` fields consistent.
- **No placeholders:** full code, exact commands, expected outcomes. (Test helper imports noted as inline.)
