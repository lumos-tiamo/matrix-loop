# Content-Level Closed Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the content loop — pull each published post's REAL performance back in, attribute it to the video/script that produced it, and bias the next topic/script toward what actually worked, so the system self-corrects on real results instead of just generating.

**Architecture:** The loop engine already consumes `ContentItem`s (`hit_content` 爆文 detection + `analyze_positioning`). So the closure is: (1) attribute `ContentItem` to its source video/draft; (2) a `refresh_published_analytics` job that pulls `work_analytics(platform_work_id)` for each `PublishDispatch` and upserts the real metrics into an attributed `ContentItem`; (3) a `content_performance` summary that biases script generation toward winners; (4) the loop surfaces a real-performance-driven correction recommendation. Real data flows in → existing loop machinery + new feedback → next content leans into winners → loop closed.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, pytest. Backend Python: `backend/.venv/bin/python`; run pytest from `backend/`.

**Scope:** Backend closure. Real data requires publishing via AiToEarn (so `platform_work_id` exists) + AiToEarn reachable for `work_analytics`; all logic is fake-client tested and runs end-to-end offline. No frontend change (the performance recommendation shows in the existing loop-run/review UI).

Preconditions: on `main`, clean, `git checkout -b feat/content-closed-loop`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 226 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `backend/app/models.py` (modify) — `ContentItem.video_asset_id` + `draft_id`.
- `backend/app/publish/analytics.py` (create) — `refresh_published_analytics`.
- `backend/app/api/routes.py` (modify) — `POST /publish/refresh-analytics`.
- `backend/app/analysis/performance.py` (create) — `content_performance` + `performance_prompt_block`.
- `backend/app/analysis/script.py` (modify) — `build_script_prompt`/`generate_script` accept `performance`.
- `backend/app/loop/engine.py` (modify) — `_build_outputs` adds a content-performance recommendation.
- Tests: `test_models_content_attribution.py`, `test_publish_analytics.py`, `test_content_performance.py`, `test_loop_content_perf.py` (create); extend `test_api_video.py` / `test_generate_script.py` as noted.

---

### Task 1: `ContentItem` attribution columns

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models_content_attribution.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, ContentItem, Draft, LoopRun, VideoAsset


def test_content_item_attribution_columns(session):
    acc = Account(platform="tiktok", handle="@x"); session.add(acc); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="s"); session.add(d); session.commit()
    v = VideoAsset(account_id=acc.id, script_draft_id=d.id, provider="fake", dedup_key="k"); session.add(v); session.commit()
    ci = ContentItem(account_id=acc.id, platform_post_id="w1", views=100, video_asset_id=v.id, draft_id=d.id)
    session.add(ci); session.commit()
    got = session.get(ContentItem, ci.id)
    assert got.video_asset_id == v.id and got.draft_id == d.id
    # defaults to None when unset
    ci2 = ContentItem(account_id=acc.id, topic="t"); session.add(ci2); session.commit()
    assert ci2.video_asset_id is None and ci2.draft_id is None
```

- [ ] **Step 2: Run — expect FAIL** (`ContentItem` has no `video_asset_id`). `./.venv/bin/python -m pytest tests/test_models_content_attribution.py -q`

- [ ] **Step 3: Add the columns**

In `backend/app/models.py`, in `class ContentItem`, after the `saves` column, add:

```python
    video_asset_id: Mapped[int | None] = mapped_column(ForeignKey("video_assets.id"), nullable=True, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True, index=True)
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_content_attribution.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(models): ContentItem source attribution (video_asset_id, draft_id)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: recreate dev DB after this plan (`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`).

---

### Task 2: `refresh_published_analytics` + route

**Files:** Create `backend/app/publish/analytics.py`; Modify `backend/app/api/routes.py`; Test `backend/tests/test_publish_analytics.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from app.models import Account, ContentItem, Draft, LoopRun, PublishDispatch, VideoAsset
from app.publish.analytics import refresh_published_analytics


class _FakeClient:
    def __init__(self, payload): self._p = payload; self.calls = []
    def work_analytics(self, platform, work_id, account_id, since=None, until=None):
        self.calls.append((platform, work_id, account_id)); return self._p


def _published(session):
    acc = Account(platform="tiktok", handle="@x", external_ref="ae_1"); session.add(acc); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    d = Draft(loop_run_id=lr.id, kind="script", content="crypto airdrop guide script", review_status="adopted")
    session.add(d); session.commit()
    v = VideoAsset(account_id=acc.id, script_draft_id=d.id, provider="fake", dedup_key="k", review_status="approved")
    session.add(v); session.commit()
    disp = PublishDispatch(account_id=acc.id, video_asset_id=v.id, platform_work_id="w9", status="published")
    session.add(disp); session.commit()
    return acc, v, d, disp


def test_refresh_backfills_attributed_content_item(session):
    acc, v, d, disp = _published(session)
    client = _FakeClient({"metrics": {"viewCount": 12000, "likeCount": 800, "commentCount": 45},
                          "work": {"publishedAt": "2026-07-08T10:00:00+00:00"}})
    report = refresh_published_analytics(session, client=client)
    assert report["refreshed"] == 1
    assert client.calls == [("tiktok", "w9", "ae_1")]
    ci = session.query(ContentItem).filter_by(account_id=acc.id, platform_post_id="w9").one()
    assert ci.views == 12000 and ci.likes == 800 and ci.comments == 45
    assert ci.video_asset_id == v.id and ci.draft_id == d.id        # attributed
    assert ci.topic and "crypto airdrop" in ci.topic                # topic snippet from script


def test_refresh_is_idempotent(session):
    acc, v, d, disp = _published(session)
    client = _FakeClient({"metrics": {"viewCount": 5, "likeCount": 1, "commentCount": 0}, "work": {}})
    refresh_published_analytics(session, client=client)
    refresh_published_analytics(session, client=client)
    assert session.query(ContentItem).filter_by(account_id=acc.id, platform_post_id="w9").count() == 1  # no dup


def test_refresh_skips_dispatches_without_work_id(session):
    acc = Account(platform="tiktok", handle="@y", external_ref="ae_2"); session.add(acc); session.commit()
    session.add(PublishDispatch(account_id=acc.id, status="queued")); session.commit()  # no platform_work_id
    report = refresh_published_analytics(session, client=_FakeClient({}))
    assert report["refreshed"] == 0
```

- [ ] **Step 2: Run — expect FAIL** (module missing).

- [ ] **Step 3: Implement**

Create `backend/app/publish/analytics.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import Account, ContentItem, Draft, PublishDispatch, VideoAsset

logger = logging.getLogger(__name__)


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def refresh_published_analytics(session: Session, *, client) -> dict:
    """For every dispatch that has a platform_work_id, pull the post's real analytics and
    upsert an attributed ContentItem (by account_id + platform_post_id). Idempotent."""
    dispatches = session.scalars(
        select(PublishDispatch).where(PublishDispatch.platform_work_id.is_not(None))
    ).all()
    refreshed = 0
    errors: list[dict] = []
    for d in dispatches:
        acc = session.get(Account, d.account_id)
        if acc is None:
            continue
        try:
            data = client.work_analytics(
                to_aitoearn_platform(acc.platform), d.platform_work_id, acc.external_ref or ""
            ) or {}
        except Exception as exc:  # noqa: BLE001 - isolate per-dispatch upstream errors
            logger.warning("work_analytics failed for dispatch %s: %s", d.id, exc)
            errors.append({"dispatch_id": d.id, "error": str(exc)})
            continue

        metrics = data.get("metrics") or {}
        work = data.get("work") or {}

        # attribution: prefer the dispatch's draft; else the video asset's script draft
        draft_id = d.draft_id
        if draft_id is None and d.video_asset_id is not None:
            va = session.get(VideoAsset, d.video_asset_id)
            draft_id = va.script_draft_id if va else None

        ci = session.scalar(
            select(ContentItem).where(
                ContentItem.account_id == acc.id,
                ContentItem.platform_post_id == d.platform_work_id,
            )
        )
        if ci is None:
            ci = ContentItem(account_id=acc.id, platform_post_id=d.platform_work_id)
            session.add(ci)

        views = metrics.get("viewCount")
        if views is None:
            views = metrics.get("playCount")
        if views is not None:
            ci.views = views
        if metrics.get("likeCount") is not None:
            ci.likes = metrics.get("likeCount")
        if metrics.get("commentCount") is not None:
            ci.comments = metrics.get("commentCount")
        ci.type = "video"
        ci.video_asset_id = d.video_asset_id
        ci.draft_id = draft_id
        published_at = _parse_dt(work.get("publishedAt"))
        if published_at is not None:
            ci.published_at = published_at
        if not ci.topic and draft_id is not None:
            dr = session.get(Draft, draft_id)
            if dr and dr.content:
                ci.topic = dr.content[:80]
        refreshed += 1

    session.commit()
    return {"refreshed": refreshed, "errors": errors, "dispatches": len(dispatches)}
```

- [ ] **Step 4: Add the route** in `backend/app/api/routes.py` (near the other `/publish/...` routes; `_aitoearn_client_or_422` already exists):

```python
@router.post("/publish/refresh-analytics")
def refresh_publish_analytics(db: Session = Depends(get_db)) -> dict:
    client = _aitoearn_client_or_422()
    from app.publish.analytics import refresh_published_analytics
    return refresh_published_analytics(db, client=client)
```

- [ ] **Step 5: Run — expect PASS** (`tests/test_publish_analytics.py`).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/publish/analytics.py backend/app/api/routes.py backend/tests/test_publish_analytics.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(publish): refresh_published_analytics - real per-post metrics -> attributed ContentItem\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: `content_performance` + bias script generation toward winners

**Files:** Create `backend/app/analysis/performance.py`; Modify `backend/app/analysis/script.py`; Modify `backend/app/api/routes.py` (generate-script route); Test `backend/tests/test_content_performance.py` (create) + extend `backend/tests/test_generate_script.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_content_performance.py`:

```python
from app.models import Account, ContentItem
from app.analysis.performance import content_performance, performance_prompt_block


def test_content_performance_ranks_winners_losers(session):
    acc = Account(platform="tiktok", handle="@x"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="airdrop guide", views=12000, likes=800),
        ContentItem(account_id=acc.id, topic="meme recap", views=300, likes=10),
        ContentItem(account_id=acc.id, topic="defi yields", views=5000, likes=200),
        ContentItem(account_id=acc.id, topic="no-views draft", views=None),
    ]); session.commit()
    perf = content_performance(session, acc.id)
    assert perf["count"] == 3                                  # None-views excluded
    assert perf["winners"][0]["topic"] == "airdrop guide"
    assert perf["losers"][-1]["topic"] == "meme recap"
    assert perf["median_views"] == 5000


def test_performance_prompt_block_mentions_winners_or_empty(session):
    acc = Account(platform="tiktok", handle="@y"); session.add(acc); session.commit()
    assert performance_prompt_block(content_performance(session, acc.id)) == ""   # no data -> empty
    session.add(ContentItem(account_id=acc.id, topic="airdrop guide", views=9000)); session.commit()
    block = performance_prompt_block(content_performance(session, acc.id))
    assert "airdrop guide" in block and "9000" in block
```

Extend `backend/tests/test_generate_script.py`:

```python
def test_build_script_prompt_includes_performance_when_given():
    from app.analysis.script import build_script_prompt
    perf_block = "Past content performance ... Top performers: \"airdrop guide\" (9000 views)"
    p = build_script_prompt("New topic", _Brief(), performance=perf_block)
    assert "airdrop guide" in p
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement `backend/app/analysis/performance.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem


def content_performance(session: Session, account_id: int, *, top: int = 3) -> dict:
    """Rank this account's content by real views. Excludes items with no views."""
    items = session.scalars(
        select(ContentItem)
        .where(ContentItem.account_id == account_id, ContentItem.views.is_not(None))
        .order_by(ContentItem.views.desc())
    ).all()
    if not items:
        return {"winners": [], "losers": [], "median_views": 0.0, "count": 0}
    views = sorted(i.views or 0 for i in items)
    n = len(views)
    median = float(views[n // 2] if n % 2 else (views[n // 2 - 1] + views[n // 2]) / 2)

    def _row(i):
        return {"topic": (i.topic or "")[:80], "views": i.views, "likes": i.likes}

    winners = [_row(i) for i in items[:top]]
    losers = [_row(i) for i in items[-top:]]
    return {"winners": winners, "losers": losers, "median_views": median, "count": n}


def performance_prompt_block(perf: dict) -> str:
    if not perf.get("count"):
        return ""
    def _fmt(rows):
        return "; ".join(f'"{r["topic"]}" ({r["views"]} views)' for r in rows) or "(none)"
    return (
        "Past content performance on this account — lean into what worked:\n"
        f"Top performers: {_fmt(perf['winners'])}\n"
        f"Underperformers: {_fmt(perf['losers'])}\n"
        "Bias the new topic/script toward the winning angles; avoid the ones that flopped."
    )
```

- [ ] **Step 4: Wire into `backend/app/analysis/script.py`**

Change signatures to accept an optional performance block and append it:

```python
def build_script_prompt(topic: str, brief, performance: str | None = None) -> str:
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
    if performance:
        lines += ["", performance]
    return "\n".join(lines)


def generate_script(topic: str, brief, client, performance: str | None = None) -> str:
    return client.complete(system=_SYSTEM, prompt=build_script_prompt(topic, brief, performance)).strip()
```

(Keep the existing `_SYSTEM` constant. Preserve prior behavior: existing tests call `build_script_prompt(topic, brief)` / `generate_script(topic, brief, client)` — the new param is optional, so they still pass.)

- [ ] **Step 5: Wire into the generate-script route** in `backend/app/api/routes.py` (`generate_script_route`): compute performance for the account and pass it in.

Replace the `text = generate_script(topic.content, brief, client)` line with:

```python
    from app.analysis.performance import content_performance, performance_prompt_block
    perf_block = performance_prompt_block(content_performance(db, lr.account_id))
    text = generate_script(topic.content, brief, client, performance=perf_block or None)
```

(`lr` is already fetched in the route as `db.get(LoopRun, topic.loop_run_id)`.)

- [ ] **Step 6: Run — expect PASS** (`tests/test_content_performance.py tests/test_generate_script.py tests/test_api_video.py`). Confirm the existing generate-script tests still pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/analysis/performance.py backend/app/analysis/script.py backend/app/api/routes.py backend/tests/test_content_performance.py backend/tests/test_generate_script.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(loop): content_performance biases script generation toward real winners\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Loop surfaces a real-performance correction recommendation

**Files:** Modify `backend/app/loop/engine.py` (`_build_outputs`); Test `backend/tests/test_loop_content_perf.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from app.models import Account, ContentItem, Snapshot
from app.loop.engine import run_loop


def test_loop_adds_content_performance_recommendation(session):
    acc = Account(platform="tiktok", handle="@x", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=140),
        ContentItem(account_id=acc.id, topic="airdrop guide", views=12000, likes=800),
        ContentItem(account_id=acc.id, topic="meme recap", views=200, likes=5),
    ]); session.commit()
    run = run_loop(session, acc)   # deterministic path (no llm)
    kinds = {r.kind for r in run.recommendations}
    assert "content_performance" in kinds
    perf_rec = next(r for r in run.recommendations if r.kind == "content_performance")
    assert "airdrop guide" in perf_rec.content        # names the top performer


def test_loop_no_perf_rec_when_no_view_data(session):
    acc = Account(platform="tiktok", handle="@y", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100))
    session.add(ContentItem(account_id=acc.id, topic="no views"))   # views None
    session.commit()
    run = run_loop(session, acc)
    assert "content_performance" not in {r.kind for r in run.recommendations}
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement** in `backend/app/loop/engine.py`, inside `_build_outputs`, after the `hits = hit_content(content_items)` block, add:

```python
    scored = [c for c in content_items if c.views is not None]
    if scored:
        scored.sort(key=lambda c: c.views or 0, reverse=True)
        top, low = scored[0], scored[-1]
        if (top.views or 0) > 0 and top is not low:
            recs.append(Recommendation(
                kind="content_performance",
                content=(f"表现反馈：最高「{(top.topic or '?')[:40]}」{top.views} views —— 多做此类角度；"
                         f"最低「{(low.topic or '?')[:40]}」{low.views} views —— 减少或换角度。"),
            ))
```

- [ ] **Step 4: Run — expect PASS** (`tests/test_loop_content_perf.py`).

- [ ] **Step 5: Full suite regression**

`cd backend && ./.venv/bin/python -m pytest -q` — all pass (226 baseline + new).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/loop/engine.py backend/tests/test_loop_content_perf.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(loop): surface real-performance content correction recommendation\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Final code review over the branch diff.
- Recreate dev DB (new ContentItem columns): `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- `superpowers:finishing-a-development-branch` → merge to `main` (`--no-ff`).
- Update `docs/DELIVERY.md`: move "闭环归因最后一环" from follow-ups to done; note real data still needs AiToEarn publishing + reachability.

## How the loop is now closed (verification narrative)

1. Human approves a video → publishes via AiToEarn → `platform_work_id` stored.
2. `POST /publish/refresh-analytics` (or scheduled) pulls the post's REAL views/likes/comments → attributed `ContentItem` (video_asset_id + draft_id + script topic).
3. Next `run_loop` evaluates those real `ContentItem`s: `hit_content` flags real 爆文, `analyze_positioning` sees real topics, and `_build_outputs` emits a `content_performance` recommendation naming the real winner/loser.
4. Next `generate-script` injects the real performance summary → the new script leans into what actually worked.
→ Real result → attributed → fed back into the next decision. **Closed.**

## Self-review

- **Coverage:** attribution (T1), real-data回流 (T2), winner-biased generation (T3), loop-surfaced correction (T4). Real data gated on AiToEarn publishing (documented); all fake-client tested.
- **Type consistency:** `refresh_published_analytics(session, *, client)`, `content_performance(session, account_id) -> dict`, `performance_prompt_block(perf) -> str`, `build_script_prompt(topic, brief, performance=None)`, `generate_script(topic, brief, client, performance=None)` — consistent across defs + call sites; optional params keep existing callers working.
- **No placeholders:** full code, exact commands, expected outcomes.
