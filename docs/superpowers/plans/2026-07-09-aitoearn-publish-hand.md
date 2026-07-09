# AiToEarn Publish Hand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human dispatch an **approved** `VideoAsset` to AiToEarn to publish/schedule (the downstream "hand"), recording a `PublishDispatch` that can be polled for status and the resulting `platformWorkId` — never auto-publishing.

**Architecture:** A new `PublishDispatch` model links an approved `VideoAsset` → AiToEarn flow/task/work ids. `POST /accounts/{id}/publish` is gated on `VideoAsset.review_status == "approved"` + a mapped `Account.external_ref` + AiToEarn configured; it builds AiToEarn's `publish/flows` payload (media = the asset's `media_url`) via the existing `AiToEarnClient` (two new methods `publish_flow`/`flow_status`), and records the dispatch. `GET /publish/dispatches/{id}` polls flow status and updates `platform_work_id`/`status`. A "发布/排期" button on approved assets in the frontend review queue drives it.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, pytest (backend); Vite + React + TS, vitest (frontend). Backend Python: `backend/.venv/bin/python`; run pytest from `backend/`, vitest from `frontend/`.

**Scope:** publish dispatch + status polling + the UI button. **Deferred (documented):** full close-the-loop attribution (pulling the published work's analytics into a `ContentItem` tagged to the recommendation/draft) — that needs the per-post ingestion follow-up; here we store `platform_work_id` so that follow-up can complete the loop. Posting-time-spread guardrail is a separate scheduler concern.

Preconditions: on `main`, clean tree, `cd /Users/aa00102/matrix-loop && git checkout -b feat/publish-hand`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 197 passed; `cd frontend && npx vitest run` → 37 passed. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `backend/app/models.py` (modify) — `PublishDispatch`.
- `backend/app/connectors/aitoearn_client.py` (modify) — `publish_flow`, `flow_status`.
- `backend/app/api/schemas.py` (modify) — `PublishIn`, `PublishDispatchOut`.
- `backend/app/api/routes.py` (modify) — `POST /accounts/{id}/publish`, `GET /publish/dispatches`, `GET /publish/dispatches/{id}`.
- `backend/app/publish/dispatch.py` (create) — `create_dispatch`, `refresh_dispatch` (the logic, so routes stay thin).
- `frontend/src/api/{types,client}.ts` (modify) — `PublishDispatchOut` type + `publish`/`listDispatches`/`refreshDispatch` methods.
- `frontend/src/pages/Video.tsx` (modify) — "发布/排期" button on approved assets + dispatch status line.
- Tests: `test_models_publish.py`, `test_aitoearn_publish_client.py`, `test_publish_dispatch.py`, `test_api_publish.py` (create); `Video.test.tsx` (extend).

---

### Task 1: `PublishDispatch` model

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_models_publish.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, PublishDispatch, VideoAsset


def test_publish_dispatch_defaults_and_persist(session):
    acc = Account(platform="tiktok", handle="@x")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4", dedup_key="k")
    session.add(v); session.commit()
    d = PublishDispatch(account_id=acc.id, video_asset_id=v.id, caption="gm",
                        media_urls=["https://f/x.mp4"])
    session.add(d); session.commit()
    got = session.get(PublishDispatch, d.id)
    assert got.status == "pending"                 # default
    assert got.media_urls == ["https://f/x.mp4"]
    assert got.aitoearn_flow_id is None and got.platform_work_id is None


def test_publish_dispatch_media_urls_default_empty(session):
    acc = Account(platform="tiktok", handle="@y")
    session.add(acc); session.commit()
    d = PublishDispatch(account_id=acc.id)
    session.add(d); session.commit()
    assert d.media_urls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_publish.py -q`
Expected: FAIL (`PublishDispatch` does not exist).

- [ ] **Step 3: Add the model**

In `backend/app/models.py`, after the `VideoAsset` class, add:

```python
class PublishDispatch(Base):
    __tablename__ = "publish_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    video_asset_id: Mapped[int | None] = mapped_column(ForeignKey("video_assets.id"), nullable=True, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"), nullable=True)
    aitoearn_flow_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    aitoearn_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_work_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")   # pending|queued|published|failed
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_urls: Mapped[list] = mapped_column(JSON, default=list)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def __init__(self, **kw):
        kw.setdefault("media_urls", list())
        super().__init__(**kw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_publish.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_publish.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(models): PublishDispatch (approved video -> AiToEarn flow/task/work)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: recreate the dev DB after this plan (`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`).

---

### Task 2: AiToEarn client `publish_flow` + `flow_status`

**Files:**
- Modify: `backend/app/connectors/aitoearn_client.py`
- Test: `backend/tests/test_aitoearn_publish_client.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.connectors.aitoearn_client import AiToEarnClient


def test_publish_flow_posts_payload_with_auth():
    seen = {}
    def fake_post(url, headers, json):
        seen["url"] = url; seen["headers"] = headers; seen["json"] = json
        return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_post=fake_post)
    out = c.publish_flow({"content": {"media": []}, "items": []})
    assert out["flowId"] == "f1"
    assert seen["url"] == "http://host/api/v2/channels/publish/flows"
    assert seen["headers"]["x-api-key"] == "KEY"
    assert seen["json"]["content"] == {"media": []}


def test_flow_status_gets_by_id():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return {"flowId": "f1", "tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_get=fake_get)
    out = c.flow_status("f1")
    assert out["tasks"][0]["platformWorkId"] == "w9"
    assert seen["url"] == "http://host/api/v2/channels/publish/flows/f1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_aitoearn_publish_client.py -q`
Expected: FAIL (`publish_flow`/`flow_status` not defined).

- [ ] **Step 3: Add the methods**

In `backend/app/connectors/aitoearn_client.py`, add to `AiToEarnClient` (after `work_analytics`):

```python
    def publish_flow(self, payload: dict) -> dict:
        url = f"{self.base_url}/channels/publish/flows"
        return self._http_post(url, self._headers(), payload) or {}

    def flow_status(self, flow_id: str) -> dict:
        url = f"{self.base_url}/channels/publish/flows/{flow_id}"
        return self._http_get(url, self._headers()) or {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_aitoearn_publish_client.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/aitoearn_client.py backend/tests/test_aitoearn_publish_client.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): AiToEarn client publish_flow + flow_status\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Dispatch logic (`create_dispatch` + `refresh_dispatch`)

**Files:**
- Create: `backend/app/publish/__init__.py` (empty), `backend/app/publish/dispatch.py`
- Test: `backend/tests/test_publish_dispatch.py` (create)

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models import Account, PublishDispatch, VideoAsset
from app.publish.dispatch import create_dispatch, refresh_dispatch, PublishNotReady


class _FakeClient:
    def __init__(self): self.published = None
    def publish_flow(self, payload):
        self.published = payload
        return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
    def flow_status(self, flow_id):
        return {"flowId": flow_id, "tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}


def _approved_asset(session, external_ref="ae_1"):
    acc = Account(platform="tiktok", handle="@x", external_ref=external_ref)
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="approved")
    session.add(v); session.commit()
    return acc, v


def test_create_dispatch_requires_approved_asset(session):
    acc = Account(platform="tiktok", handle="@x", external_ref="ae_1")
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="pending")
    session.add(v); session.commit()
    with pytest.raises(PublishNotReady):
        create_dispatch(session, acc, v, client=_FakeClient(), caption="gm")


def test_create_dispatch_requires_external_ref(session):
    acc = Account(platform="tiktok", handle="@x")   # no external_ref
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status="approved")
    session.add(v); session.commit()
    with pytest.raises(PublishNotReady):
        create_dispatch(session, acc, v, client=_FakeClient(), caption="gm")


def test_create_dispatch_publishes_and_records(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    d = create_dispatch(session, acc, v, client=client, caption="gm airdrop szn")
    # payload built correctly: media = asset url, item targets the AiToEarn accountId + mapped platform
    assert client.published["items"][0]["accountId"] == "ae_1"
    assert client.published["items"][0]["platform"] == "tiktok"
    assert client.published["content"]["media"][0]["url"] == "https://f/x.mp4"
    # dispatch recorded
    assert d.aitoearn_flow_id == "f1" and d.aitoearn_task_id == "t1"
    assert d.status == "queued"          # WaitingForPublish -> queued
    assert d.media_urls == ["https://f/x.mp4"] and d.caption == "gm airdrop szn"


def test_refresh_dispatch_updates_work_id_and_status(session):
    acc, v = _approved_asset(session)
    client = _FakeClient()
    d = create_dispatch(session, acc, v, client=client, caption="x")
    refreshed = refresh_dispatch(session, d, client=client)
    assert refreshed.platform_work_id == "w9"
    assert refreshed.status == "published"    # Published -> published
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_publish_dispatch.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement**

Create `backend/app/publish/__init__.py`:

```python
```

Create `backend/app/publish/dispatch.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import PublishDispatch, VideoAsset


class PublishNotReady(RuntimeError):
    """Raised when a video asset cannot be dispatched (not approved / account not mapped)."""


# AiToEarn task status -> our dispatch status
_STATUS_MAP = {
    "WaitingForPublish": "queued",
    "Publishing": "queued",
    "Published": "published",
    "Failed": "failed",
}


def _map_status(task_status: str | None) -> str:
    return _STATUS_MAP.get(task_status or "", "queued")


def create_dispatch(session: Session, account, asset: VideoAsset, *, client,
                    caption: str | None = None, publish_at: datetime | None = None) -> PublishDispatch:
    """Publish an APPROVED video asset via AiToEarn and record a PublishDispatch.
    Human-gated: the asset must already be human-approved; this call is the explicit publish action."""
    if asset.review_status != "approved":
        raise PublishNotReady("video asset must be human-approved before publishing")
    if not account.external_ref:
        raise PublishNotReady(f"account {account.handle} 未映射 AiToEarn accountId(external_ref)")
    if not asset.media_url:
        raise PublishNotReady("video asset has no media_url")

    when = publish_at or datetime.now(timezone.utc)
    payload = {
        "content": {
            "title": caption or "",
            "body": caption or "",
            "media": [{"url": asset.media_url, "options": {}}],
        },
        "publishAt": when.isoformat(),
        "items": [{
            "accountId": account.external_ref,
            "platform": to_aitoearn_platform(account.platform),
        }],
    }
    resp = client.publish_flow(payload) or {}
    tasks = resp.get("tasks") or []
    task = tasks[0] if tasks else {}
    dispatch = PublishDispatch(
        account_id=account.id,
        video_asset_id=asset.id,
        aitoearn_flow_id=resp.get("flowId"),
        aitoearn_task_id=task.get("id"),
        platform_work_id=task.get("platformWorkId"),
        status=_map_status(task.get("status")),
        publish_at=when,
        media_urls=[asset.media_url],
        caption=caption,
    )
    session.add(dispatch)
    session.commit()
    return dispatch


def refresh_dispatch(session: Session, dispatch: PublishDispatch, *, client) -> PublishDispatch:
    """Poll AiToEarn for the flow's current status; update platform_work_id + status."""
    if not dispatch.aitoearn_flow_id:
        return dispatch
    resp = client.flow_status(dispatch.aitoearn_flow_id) or {}
    tasks = resp.get("tasks") or []
    # prefer the task we recorded; else the first
    task = next((t for t in tasks if t.get("id") == dispatch.aitoearn_task_id), tasks[0] if tasks else {})
    if task.get("platformWorkId"):
        dispatch.platform_work_id = task["platformWorkId"]
    dispatch.status = _map_status(task.get("status"))
    session.commit()
    return dispatch
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_publish_dispatch.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/publish/ backend/tests/test_publish_dispatch.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(publish): create_dispatch + refresh_dispatch (approved video -> AiToEarn, gated)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Publish + dispatch APIs

**Files:**
- Modify: `backend/app/api/schemas.py` (`PublishIn`, `PublishDispatchOut`)
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_api_publish.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.models import Account, VideoAsset


def _approved(session, external_ref="ae_1", review="approved"):
    acc = Account(platform="tiktok", handle="@x", external_ref=external_ref)
    session.add(acc); session.commit()
    v = VideoAsset(account_id=acc.id, provider="fake", media_url="https://f/x.mp4",
                   dedup_key="k", status="ready", review_status=review)
    session.add(v); session.commit()
    return acc, v


def test_publish_requires_aitoearn_configured(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", None, raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", None, raising=False)
    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id, "caption": "gm"})
    assert r.status_code == 422


def test_publish_dispatches_approved_asset(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)

    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload):
            return {"flowId": "f1", "tasks": [{"id": "t1", "platform": "tiktok", "status": "WaitingForPublish"}]}
        def flow_status(self, fid):
            return {"tasks": [{"id": "t1", "status": "Published", "platformWorkId": "w9"}]}
    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)

    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id, "caption": "gm"})
    assert r.status_code == 201
    body = r.json()
    assert body["aitoearn_flow_id"] == "f1" and body["status"] == "queued"
    did = body["id"]
    # poll
    r2 = client.get(f"/publish/dispatches/{did}")
    assert r2.status_code == 200
    assert r2.json()["platform_work_id"] == "w9" and r2.json()["status"] == "published"


def test_publish_rejects_unapproved(client, session, monkeypatch):
    acc, v = _approved(session, review="pending")
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    monkeypatch.setattr("app.api.routes.AiToEarnClient", lambda *a, **k: None)
    r = client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id})
    assert r.status_code == 422


def test_list_dispatches(client, session, monkeypatch):
    acc, v = _approved(session)
    from app.config import settings
    monkeypatch.setattr(settings, "aitoearn_base_url", "http://x/api/v2", raising=False)
    monkeypatch.setattr(settings, "aitoearn_api_key", "k", raising=False)
    class _FakeClient:
        def __init__(self, *a, **k): pass
        def publish_flow(self, payload): return {"flowId": "f1", "tasks": [{"id": "t1", "status": "WaitingForPublish"}]}
    monkeypatch.setattr("app.api.routes.AiToEarnClient", _FakeClient)
    client.post(f"/accounts/{acc.id}/publish", json={"video_asset_id": v.id})
    rows = client.get(f"/publish/dispatches?account_id={acc.id}").json()
    assert len(rows) == 1 and rows[0]["video_asset_id"] == v.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_publish.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add schemas**

In `backend/app/api/schemas.py` add:

```python
class PublishIn(BaseModel):
    video_asset_id: int
    caption: str | None = None
    publish_at: datetime | None = None


class PublishDispatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    video_asset_id: int | None
    aitoearn_flow_id: str | None
    aitoearn_task_id: str | None
    platform_work_id: str | None
    status: str
    publish_at: datetime | None
    media_urls: list[str]
    caption: str | None
    created_at: datetime
```

- [ ] **Step 4: Add routes**

In `backend/app/api/routes.py`: add `PublishDispatch` to the `from app.models import ...` line, and `from app.connectors.aitoearn_client import AiToEarnClient` at the top (it may already be imported for linking — verify, don't duplicate). Add these routes (register `GET /publish/dispatches` and `/publish/dispatches/{id}` — both 2/3-segment static prefixes, no collision):

```python
def _aitoearn_client_or_422() -> AiToEarnClient:
    from app.config import settings
    if not (settings.aitoearn_base_url and settings.aitoearn_api_key):
        raise HTTPException(status_code=422, detail="AiToEarn 未配置(MATRIXLOOP_AITOEARN_BASE_URL/API_KEY)")
    return AiToEarnClient(settings.aitoearn_base_url, settings.aitoearn_api_key)


@router.post("/accounts/{account_id}/publish", response_model=schemas.PublishDispatchOut, status_code=201)
def publish_account(account_id: int, payload: schemas.PublishIn, db: Session = Depends(get_db)) -> PublishDispatch:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    asset = db.get(VideoAsset, payload.video_asset_id)
    if asset is None or asset.account_id != account_id:
        raise HTTPException(status_code=404, detail="video asset not found for this account")
    client = _aitoearn_client_or_422()
    from app.publish.dispatch import create_dispatch, PublishNotReady
    try:
        return create_dispatch(db, acc, asset, client=client, caption=payload.caption, publish_at=payload.publish_at)
    except PublishNotReady as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - upstream connector error
        logger.warning("publish failed for account %s: %s", account_id, exc)
        raise HTTPException(status_code=502, detail="upstream publish error") from exc


@router.get("/publish/dispatches", response_model=list[schemas.PublishDispatchOut])
def list_dispatches(account_id: int | None = None, db: Session = Depends(get_db)) -> list[PublishDispatch]:
    stmt = select(PublishDispatch).order_by(PublishDispatch.id.desc())
    if account_id is not None:
        stmt = stmt.where(PublishDispatch.account_id == account_id)
    return list(db.scalars(stmt).all())


@router.get("/publish/dispatches/{dispatch_id}", response_model=schemas.PublishDispatchOut)
def get_dispatch(dispatch_id: int, db: Session = Depends(get_db)) -> PublishDispatch:
    d = db.get(PublishDispatch, dispatch_id)
    if d is None:
        raise HTTPException(status_code=404, detail="dispatch not found")
    from app.publish.dispatch import refresh_dispatch
    try:
        return refresh_dispatch(db, d, client=_aitoearn_client_or_422())
    except HTTPException:
        return d   # AiToEarn not configured -> return stored state without polling
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_api_publish.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Full backend suite**

Run: `cd backend && ./.venv/bin/python -m pytest -q`
Expected: all pass (197 baseline + new).

- [ ] **Step 7: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/schemas.py backend/app/api/routes.py backend/tests/test_api_publish.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(api): POST /accounts/{id}/publish + GET /publish/dispatches[/{id}] (poll)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Frontend — publish button + dispatch status on the review queue

**Files:**
- Modify: `frontend/src/api/types.ts` (`PublishDispatchOut`)
- Modify: `frontend/src/api/client.ts` (`publish`, `listDispatches`, `refreshDispatch`)
- Modify: `frontend/src/pages/Video.tsx` (ReviewQueue: 发布 button on approved assets + dispatch status)
- Test: `frontend/src/pages/Video.test.tsx` (extend)

- [ ] **Step 1: Add type + client methods**

In `frontend/src/api/types.ts` add:

```ts
export interface PublishDispatchOut {
  id: number;
  account_id: number;
  video_asset_id: number | null;
  aitoearn_flow_id: string | null;
  aitoearn_task_id: string | null;
  platform_work_id: string | null;
  status: string;
  publish_at: string | null;
  media_urls: string[];
  caption: string | null;
  created_at: string;
}
```

In `frontend/src/api/client.ts` (import `PublishDispatchOut` from types) add to `api`:

```ts
  publish: (accountId: number, videoAssetId: number, caption?: string) =>
    req<PublishDispatchOut>(`/accounts/${accountId}/publish`, {
      method: "POST", body: JSON.stringify({ video_asset_id: videoAssetId, caption: caption ?? null }),
    }),
  listDispatches: (accountId: number) =>
    req<PublishDispatchOut[]>(`/publish/dispatches?account_id=${accountId}`),
  refreshDispatch: (id: number) => req<PublishDispatchOut>(`/publish/dispatches/${id}`),
```

- [ ] **Step 2: Write the failing test**

Append to `frontend/src/pages/Video.test.tsx`:

```tsx
it("publishes an approved asset via 发布", async () => {
  const calls: string[] = [];
  const approved = { ...ASSET, review_status: "approved" };
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([]) };
    if (url.match(/\/accounts\/4\/publish$/) && init?.method === "POST") {
      calls.push("publish");
      return { ok: true, json: async () => ({ id: 1, account_id: 4, video_asset_id: 9, aitoearn_flow_id: "f1", aitoearn_task_id: "t1", platform_work_id: null, status: "queued", publish_at: null, media_urls: [], caption: "x", created_at: "2026-07-09T00:00:00Z" }) };
    }
    if (url.includes("/publish/dispatches")) return { ok: true, json: async () => [] };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [approved] };
    return undefined;
  });
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  fireEvent.click(await screen.findByRole("button", { name: /发布/ }));
  await waitFor(() => expect(calls).toContain("publish"));
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: FAIL (no 发布 button).

- [ ] **Step 4: Implement in `ReviewQueue`**

In `frontend/src/pages/Video.tsx`, in `ReviewQueue`, add a publish action for `approved` assets. Add to the row (after the pending approve/reject block), a branch for approved assets:

```tsx
            {v.review_status === "approved" && (
              <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet`} disabled={busy === v.id}
                onClick={() => publish(v.id)}>{busy === v.id ? "发布中…" : "发布/排期"}</button>
            )}
```

And add the `publish` handler inside `ReviewQueue` (alongside `review`):

```tsx
  async function publish(assetId: number) {
    setBusy(assetId); setMsg(null);
    try { await api.publish(accountId, assetId); setMsg("已提交发布(见 AiToEarn)"); assets.reload(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(null); }
  }
```

(`accountId` is already a prop of `ReviewQueue`; `busy`/`setMsg`/`assets` already exist from Task 4/5 of the frontend plan.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: PASS (8 tests total in the file).

- [ ] **Step 6: Full frontend suite + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: no type errors; all pass (37 baseline + 1 new = 38).

- [ ] **Step 7: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): 发布/排期 button on approved videos -> AiToEarn publish hand\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Dispatch a final code review over the branch diff (`git diff main..HEAD`).
- Recreate the dev DB for the new table: `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- Use `superpowers:finishing-a-development-branch` to merge to `main` (option 1, `--no-ff`).
- Live dogfood (manual, needs AiToEarn running + a mapped account with `external_ref`): approve a video on `/video`, click 发布/排期, then confirm a `PublishDispatch` appears and `GET /publish/dispatches/{id}` reflects the AiToEarn flow status.

## Deferred follow-ups (documented)

- Full close-the-loop attribution: pull the published work's analytics (via `AiToEarnConnector.work_analytics` using the stored `platform_work_id`) into a `ContentItem` tagged to the originating recommendation/draft — needs the per-post ingestion follow-up.
- Media hosting: `media_url` must be reachable by AiToEarn; if videos are generated to local files, upload to AiToEarn's S3 first (thin proxy) — future.
- Posting-time-spread guardrail at dispatch time (scheduler concern).

## Self-review notes (against the spec)

- **Spec coverage:** `PublishDispatch` (Task 1); client `publish_flow`/`flow_status` (Task 2); `create_dispatch`/`refresh_dispatch` gated on approved asset + external_ref + configured AiToEarn (Task 3); `POST /accounts/{id}/publish` + `GET /publish/dispatches[/{id}]` (Task 4); UI 发布 button (Task 5). Close-the-loop attribution correctly deferred (platform_work_id is stored to enable it).
- **Type consistency:** `create_dispatch(session, account, asset, *, client, caption=None, publish_at=None)` matches call sites; `_map_status` covers WaitingForPublish/Publishing/Published/Failed; `PublishDispatchOut` fields match the model; client method names match usage.
- **Human-in-loop:** publish is gated on `review_status == "approved"` and is an explicit endpoint/button — never automatic.
- **No placeholders:** every step has full code, exact commands, expected outcomes.
