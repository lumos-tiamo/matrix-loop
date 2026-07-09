# Trend Ingestion + Unattended Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Complete the flywheel's two open pieces — ① a **trend store + ingestion + wiring** so scraped viral crypto trends seed content generation and light up the flywheel's `crawl` node; ② an **unattended scheduler switch** so the autopilot cycle can run after hours (default OFF for safety, startable via config or API).

**Architecture:** ① A `Trend` table + `POST /trends/ingest` (agent-driven: an agent running agent-reach distills viral crypto content and posts it) + `GET /trends`; `trend_prompt_block` formats recent trends into a prompt block wired into script generation (scripts become trend-aware) and the flywheel `crawl` step count reflects real trends. ② A module-level scheduler holder (`start_scheduler`/`stop_scheduler`/`scheduler_running`) + a FastAPI lifespan hook that auto-starts when `scheduler_autostart=True` + `POST /flywheel/scheduler/start|stop` and status exposure. Real trend scraping stays agent-driven (agent-reach isn't callable from the FastAPI process) — the backend owns the store + wiring; this is the honest boundary.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, APScheduler, pytest. Backend Python: `backend/.venv/bin/python`; run pytest from `backend/`.

Preconditions: on `main`, clean, `git checkout -b feat/trends-unattended`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 254 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `backend/app/models.py` (modify) — `Trend`.
- `backend/app/analysis/trends.py` (create) — `trend_prompt_block`.
- `backend/app/analysis/script.py` (modify) — `build_script_prompt`/`generate_script` accept `trends`.
- `backend/app/api/schemas.py` (modify) — `TrendIn`, `TrendIngest`.
- `backend/app/api/routes.py` (modify) — `POST /trends/ingest`, `GET /trends`, generate-script wiring, scheduler start/stop.
- `backend/app/orchestrator/engine.py` (modify) — pass trends into autopilot script gen.
- `backend/app/orchestrator/state.py` (modify) — `crawl` step count from trends.
- `backend/app/config.py` (modify) — `scheduler_autostart`.
- `backend/app/scheduler/control.py` (create) — scheduler holder.
- `backend/app/main.py` (modify) — lifespan autostart.
- Tests: `test_models_trend.py`, `test_trends_api.py`, `test_trend_prompt.py`, `test_scheduler_control.py` (create).

---

### Task 1: `Trend` model

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models_trend.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Trend


def test_trend_persist_defaults(session):
    t = Trend(source="tiktok", title="Airdrop farming blew up", niche="airdrop",
              engagement=120000, distilled_topic="How to farm the next big airdrop")
    session.add(t); session.commit()
    got = session.query(Trend).one()
    assert got.source == "tiktok" and got.niche == "airdrop"
    assert got.score == 0.0 and got.url is None and got.captured_at is not None
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** — in `backend/app/models.py`, add at end:

```python
class Trend(Base):
    __tablename__ = "trends"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(24))                       # tiktok|youtube|x|web
    title: Mapped[str] = mapped_column(String)                           # the viral piece / headline
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    niche: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    engagement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distilled_topic: Mapped[str | None] = mapped_column(String, nullable=True)  # LLM-distilled angle to make
    score: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit** `git add backend/app/models.py backend/tests/test_models_trend.py` → `feat(models): Trend (viral-content trend store)`.

Note: recreate dev DB after this plan.

---

### Task 2: Trends ingest + list API + flywheel crawl count

**Files:** Modify `backend/app/api/schemas.py`, `backend/app/api/routes.py`, `backend/app/orchestrator/state.py`; Test `backend/tests/test_trends_api.py` (create)

- [ ] **Step 1: Write the failing test**

```python
def test_ingest_and_list_trends(client, session):
    body = {"trends": [
        {"source": "tiktok", "title": "Airdrop szn is back", "niche": "airdrop", "engagement": 90000,
         "distilled_topic": "3 airdrops to farm this week", "url": "https://t/1"},
        {"source": "youtube", "title": "DeFi yields explained", "niche": "defi", "engagement": 40000},
    ]}
    r = client.post("/trends/ingest", json=body)
    assert r.status_code == 201 and r.json()["ingested"] == 2
    # idempotent: re-post same -> skipped, no dup
    r2 = client.post("/trends/ingest", json=body)
    assert r2.json()["ingested"] == 0 and r2.json()["skipped"] == 2
    rows = client.get("/trends").json()
    assert len(rows) == 2
    airdrop = client.get("/trends?niche=airdrop").json()
    assert len(airdrop) == 1 and airdrop[0]["distilled_topic"] == "3 airdrops to farm this week"


def test_flywheel_crawl_count_reflects_trends(client, session):
    client.post("/trends/ingest", json={"trends": [
        {"source": "tiktok", "title": "t1"}, {"source": "x", "title": "t2"}]})
    fw = client.get("/flywheel").json()
    crawl = next(s for s in fw["steps"] if s["key"] == "crawl")
    assert crawl["count"] == 2 and crawl["status"] == "ok"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Add schemas** — in `backend/app/api/schemas.py`:

```python
class TrendIn(BaseModel):
    source: str
    title: str
    url: str | None = None
    niche: str | None = None
    engagement: int | None = None
    distilled_topic: str | None = None
    score: float = 0.0


class TrendIngest(BaseModel):
    trends: list[TrendIn]
```

- [ ] **Step 4: Add routes** — in `backend/app/api/routes.py` (add `Trend` to the `from app.models import ...` line):

```python
@router.post("/trends/ingest", status_code=201)
def ingest_trends(payload: schemas.TrendIngest, db: Session = Depends(get_db)) -> dict:
    ingested = skipped = 0
    for t in payload.trends:
        existing = db.scalar(select(Trend).where(Trend.source == t.source, Trend.title == t.title))
        if existing is not None:
            skipped += 1
            continue
        db.add(Trend(source=t.source, title=t.title, url=t.url, niche=t.niche,
                     engagement=t.engagement, distilled_topic=t.distilled_topic, score=t.score))
        ingested += 1
    db.commit()
    return {"ingested": ingested, "skipped": skipped}


@router.get("/trends")
def list_trends(niche: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Trend).order_by(Trend.captured_at.desc(), Trend.id.desc())
    if niche:
        stmt = stmt.where(Trend.niche == niche)
    stmt = stmt.limit(limit)
    return [{"id": t.id, "source": t.source, "title": t.title, "url": t.url, "niche": t.niche,
             "engagement": t.engagement, "distilled_topic": t.distilled_topic, "score": t.score,
             "captured_at": t.captured_at.isoformat() if t.captured_at else None}
            for t in db.scalars(stmt).all()]
```

- [ ] **Step 5: Wire crawl count** — in `backend/app/orchestrator/state.py` `flywheel_state`, replace the hardcoded crawl step. Add near the other counts: `trends_n = _count(_select(func.count(Trend.id)))` (import `Trend`), and change the crawl step dict to `{"key": "crawl", "label": "爬爆款", "count": trends_n, "status": "ok" if trends_n else "pending"}`.

- [ ] **Step 6: Run — expect PASS** (`tests/test_trends_api.py`).

- [ ] **Step 7: Commit** `git add backend/app/api/schemas.py backend/app/api/routes.py backend/app/orchestrator/state.py backend/tests/test_trends_api.py` → `feat(api): trends ingest/list + flywheel crawl count`.

---

### Task 3: Trend-aware script generation

**Files:** Create `backend/app/analysis/trends.py`; Modify `backend/app/analysis/script.py`, `backend/app/api/routes.py` (generate-script), `backend/app/orchestrator/engine.py`; Test `backend/tests/test_trend_prompt.py` (create) + extend `test_generate_script.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_trend_prompt.py`:

```python
from app.models import Trend
from app.analysis.trends import trend_prompt_block


def test_trend_block_empty(session):
    assert trend_prompt_block(session) == ""


def test_trend_block_lists_recent(session):
    session.add_all([
        Trend(source="tiktok", title="Airdrop szn", niche="airdrop", distilled_topic="Farm 3 airdrops now"),
        Trend(source="x", title="Meme rotation", niche="meme", distilled_topic="Why memes pump Fridays"),
    ]); session.commit()
    block = trend_prompt_block(session)
    assert "Farm 3 airdrops now" in block or "Airdrop szn" in block
    # niche filter
    b2 = trend_prompt_block(session, niches=["airdrop"])
    assert "airdrop" in b2.lower() and "meme rotation" not in b2.lower()
```

Extend `backend/tests/test_generate_script.py`:

```python
def test_build_script_prompt_includes_trends_when_given():
    from app.analysis.script import build_script_prompt
    p = build_script_prompt("Topic", _Brief(), trends="Trending now: \"Farm 3 airdrops\" (tiktok)")
    assert "Farm 3 airdrops" in p
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `backend/app/analysis/trends.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trend


def trend_prompt_block(session: Session, niches: list[str] | None = None, *, limit: int = 8) -> str:
    """Format recent viral trends into a prompt block so generation leans into what's hot now."""
    stmt = select(Trend).order_by(Trend.captured_at.desc(), Trend.id.desc())
    if niches:
        stmt = stmt.where(Trend.niche.in_(niches))
    rows = list(session.scalars(stmt.limit(limit)).all())
    if not rows:
        return ""
    lines = []
    for t in rows:
        angle = t.distilled_topic or t.title
        tag = f" [{t.niche}]" if t.niche else ""
        lines.append(f'- "{angle}" ({t.source}{tag})')
    return "Currently trending viral angles — lean into what's hot right now:\n" + "\n".join(lines)
```

- [ ] **Step 4: Wire into `backend/app/analysis/script.py`** — add `trends` param:

```python
def build_script_prompt(topic: str, brief, performance: str | None = None, trends: str | None = None) -> str:
    lines = [
        f"Channel main direction: {getattr(brief, 'main_direction', '')}",
        f"Sub-niches: {'、'.join(getattr(brief, 'sub_niches', None) or []) or '(none)'}",
        f"Host persona: {getattr(brief, 'persona', None) or '(faceless voiceover)'}",
        f"Tone: {getattr(brief, 'tone', None) or 'clear and energetic'}",
        f"Language: {getattr(brief, 'language', None) or 'en'}",
        f"Topic for this video: {topic}",
        "",
        "Compliance: frame as information/education only, NOT investment advice or a "
        "trading solicitation. Avoid promises of returns.",
    ]
    if trends:
        lines += ["", trends]
    if performance:
        lines += ["", performance]
    return "\n".join(lines)


def generate_script(topic: str, brief, client, performance: str | None = None, trends: str | None = None) -> str:
    return client.complete(system=_SYSTEM,
                           prompt=build_script_prompt(topic, brief, performance, trends)).strip()
```

- [ ] **Step 5: Wire into callers**

In `backend/app/api/routes.py` `generate_script_route`, compute trends and pass them (add import `from app.analysis.trends import trend_prompt_block` at top):

```python
    perf_block = performance_prompt_block(content_performance(db, lr.account_id))
    niches = brief.sub_niches if brief else None
    trend_block = trend_prompt_block(db, niches)
    text = generate_script(topic.content, brief, client, performance=perf_block, trends=trend_block or None)
```

In `backend/app/orchestrator/engine.py` `advance_account`, where it calls `generate_script(topic.content, brief, llm, performance=perf or None)`, also pass trends (add `from app.analysis.trends import trend_prompt_block` at top):

```python
    perf = performance_prompt_block(content_performance(session, account.id))
    trends = trend_prompt_block(session, brief.sub_niches if brief else None)
    text = generate_script(topic.content, brief, llm, performance=perf or None, trends=trends or None)
```

- [ ] **Step 6: Run — expect PASS** (`tests/test_trend_prompt.py tests/test_generate_script.py tests/test_orchestrator_advance.py`). Confirm existing generate-script + orchestrator tests still pass (the new param is optional).

- [ ] **Step 7: Commit** `git add backend/app/analysis/trends.py backend/app/analysis/script.py backend/app/api/routes.py backend/app/orchestrator/engine.py backend/tests/test_trend_prompt.py backend/tests/test_generate_script.py` → `feat(loop): trend-aware script generation (viral trends seed content)`.

---

### Task 4: Scheduler control module

**Files:** Create `backend/app/scheduler/control.py`; Modify `backend/app/config.py`; Test `backend/tests/test_scheduler_control.py` (create)

- [ ] **Step 1: Write the failing test**

```python
def test_scheduler_control_start_stop():
    from app.scheduler import control
    control.stop_scheduler()                      # idempotent even if not started
    assert control.scheduler_running() is False
    control.start_scheduler(lambda: None, interval_minutes=60)
    assert control.scheduler_running() is True
    # idempotent start
    control.start_scheduler(lambda: None, interval_minutes=60)
    assert control.scheduler_running() is True
    control.stop_scheduler()
    assert control.scheduler_running() is False
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Config** — in `backend/app/config.py` `Settings`, add `scheduler_autostart: bool = False`.

- [ ] **Step 4: Implement `backend/app/scheduler/control.py`**

```python
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
```

- [ ] **Step 5: Run — expect PASS.** (Stop the scheduler at test end to avoid a lingering thread — the test does.)

- [ ] **Step 6: Commit** `git add backend/app/scheduler/control.py backend/app/config.py backend/tests/test_scheduler_control.py` → `feat(scheduler): start/stop control holder + autostart config`.

---

### Task 5: Lifespan autostart + scheduler API + status

**Files:** Modify `backend/app/main.py`, `backend/app/api/routes.py`, `backend/app/orchestrator/state.py`; Test `backend/tests/test_scheduler_control.py` (extend, API part)

- [ ] **Step 1: Write the failing test**

```python
def test_scheduler_api_start_status_stop(client):
    assert client.get("/flywheel/status").json().get("scheduler_running") is False
    r = client.post("/flywheel/scheduler/start")
    assert r.status_code == 200 and r.json()["scheduler_running"] is True
    assert client.get("/flywheel/status").json()["scheduler_running"] is True
    assert client.post("/flywheel/scheduler/stop").json()["scheduler_running"] is False
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Lifespan autostart** — in `backend/app/main.py`, add a startup hook that auto-starts the scheduler only when configured:

```python
@app.on_event("startup")
def _maybe_autostart_scheduler() -> None:
    from app.config import settings
    if settings.scheduler_autostart:
        from app.scheduler.control import start_scheduler
        from app.db import SessionLocal
        start_scheduler(SessionLocal)
```

- [ ] **Step 4: Scheduler API + status** — in `backend/app/api/routes.py` (import `from app.scheduler.control import start_scheduler, stop_scheduler, scheduler_running`; `SessionLocal` is already imported):

```python
@router.post("/flywheel/scheduler/start")
def scheduler_start() -> dict:
    start_scheduler(SessionLocal)
    return {"scheduler_running": scheduler_running()}


@router.post("/flywheel/scheduler/stop")
def scheduler_stop() -> dict:
    stop_scheduler()
    return {"scheduler_running": scheduler_running()}
```

Update `flywheel_status` to include scheduler state:

```python
@router.get("/flywheel/status")
def flywheel_status(db: Session = Depends(get_db)) -> dict:
    return {"paused": is_paused(db), "scheduler_running": scheduler_running()}
```

Also add `scheduler_running` into `GET /flywheel` payload: in `backend/app/orchestrator/state.py` `flywheel_state`, add `"scheduler_running": None` is not needed — instead the route can merge it. Simplest: in the `flywheel` route, do `return {**flywheel_state(db), "scheduler_running": scheduler_running()}` (import `scheduler_running` in routes; keep `flywheel_state` pure).

- [ ] **Step 5: Run — expect PASS** (`tests/test_scheduler_control.py`). Ensure the test stops the scheduler at the end so no thread leaks into other tests.

- [ ] **Step 6: Full suite regression** — `cd backend && ./.venv/bin/python -m pytest -q` — all pass (254 baseline + new). If a lingering scheduler thread affects other tests, ensure `stop_scheduler()` is called in the test (and consider an autouse fixture in that test file to stop after each).

- [ ] **Step 7: Commit** `git add backend/app/main.py backend/app/api/routes.py backend/app/orchestrator/state.py backend/tests/test_scheduler_control.py` → `feat(api): unattended scheduler start/stop + lifespan autostart + status`.

---

## After all tasks

- Final code review over the branch diff.
- Recreate dev DB (new `trends` table): `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- `superpowers:finishing-a-development-branch` → merge to `main` (`--no-ff`).
- **Live demo of real trend scraping** (agent-driven, done by the controlling agent, not the backend): run agent-reach to fetch real crypto/web3 viral short-video trends, distill to `{source,title,niche,distilled_topic,engagement}`, `POST /trends/ingest` → the flywheel `crawl` node lights up with real data and new scripts become trend-aware.
- Update `docs/DELIVERY.md`: trend ingestion + unattended scheduler done; note real trend scraping is agent-driven (agent-reach → ingest) and the scheduler is OFF unless `MATRIXLOOP_SCHEDULER_AUTOSTART=true` or `POST /flywheel/scheduler/start`.

## Deferred / honest boundary

- Backend cannot itself run agent-reach (a Claude-side skill). Trend scraping is agent-driven: a scheduled agent (me / OpenClaw / a cron Claude run) runs agent-reach, distills, and POSTs to `/trends/ingest`. The backend owns the store, wiring, and flywheel display. A fully backend-native trend fetch would need a programmatic web-search/trends API key — a future `TrendProvider` seam (not built here).
- Topic-level trend seeding (into `analyze_positioning.suggested_topics`) is a follow-up; this plan seeds the SCRIPT stage (trend-aware scripts) + surfaces trends on the flywheel.

## Self-review

- **Coverage:** Trend model (T1), ingest/list API + flywheel crawl count (T2), trend_prompt_block + trend-aware script gen wired into route + orchestrator (T3), scheduler control holder + autostart config (T4), lifespan autostart + scheduler API + status (T5).
- **Type consistency:** `trend_prompt_block(session, niches=None, *, limit=8)`; `build_script_prompt(topic, brief, performance=None, trends=None)` / `generate_script(..., performance=None, trends=None)` — optional params keep all existing callers working; `start_scheduler/stop_scheduler/scheduler_running` consistent across control module, lifespan, and routes.
- **Safety:** scheduler defaults OFF (no unexpected unattended runs); autostart only via explicit config/API.
- **No placeholders:** full code, exact commands, expected outcomes.
