# MatrixLoop API 层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端大脑（模型 + 导入 + 评估/分析 + Loop 引擎）暴露成 FastAPI 路由，供 Dashboard 消费：账号总览列表、单账号下钻、CSV 导入、触发一轮 Loop、采纳/否决建议与草稿。

**Architecture:** `app/api/deps.py`（`get_db` 依赖）、`app/api/schemas.py`（Pydantic v2 读写模型，读模型用 `from_attributes` 直接映射 ORM）、`app/api/routes.py`（一个 `APIRouter`），在 `app/main.py` 用 `include_router` 挂载。测试用 FastAPI `TestClient` + `dependency_overrides` 把 `get_db` 覆盖成内存 session（写入与断言共用同一 session）。Loop 触发走确定性路径（API 暂不注入 llm_client）。

**Tech Stack:** Python 3.13（同一 venv），FastAPI、Pydantic v2、pytest（均已有）。

**依赖：** 地基（models, `app/db.py` 的 `SessionLocal`）、plan 4（`run_loop`）、`app/ingest/manual_import.import_snapshots_csv`。

---

### Task 1: API 依赖 + schemas + 账号 创建/列表

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/schemas.py`
- Create: `backend/app/api/routes.py`
- Modify: `backend/app/main.py` (挂载 router)
- Modify: `backend/tests/conftest.py` (追加 `client` fixture)
- Test: `backend/tests/test_api_accounts.py`

- [ ] **Step 1: 追加 client fixture 到 conftest**

Append to `backend/tests/conftest.py`:
```python
@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_db

    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: 写失败的账号 API 测试**

Create `backend/tests/test_api_accounts.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, Evaluation, LoopRun


def test_create_account_returns_201_and_item(client):
    resp = client.post("/accounts", json={"platform": "xiaohongshu", "handle": "@a1", "vertical": "beauty"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["platform"] == "xiaohongshu"
    assert body["handle"] == "@a1"
    assert body["latest_composite_score"] is None  # 还没评估


def test_list_accounts_includes_latest_metrics(client, session):
    acc = Account(platform="douyin", handle="@a2")
    session.add(acc)
    session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc),
                         followers=12345, source_tier="manual"))
    ev = Evaluation(account_id=acc.id, composite_score=73.0, breakdown={})
    run = LoopRun(account_id=acc.id, status="no_progress")
    run.evaluation = ev
    session.add(run)
    session.commit()

    resp = client.get("/accounts")
    assert resp.status_code == 200
    items = resp.json()
    item = next(i for i in items if i["handle"] == "@a2")
    assert item["latest_followers"] == 12345
    assert item["latest_composite_score"] == 73.0
    assert item["latest_loop_status"] == "no_progress"
    assert item["source_tier"] == "manual"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_accounts.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.api'`

- [ ] **Step 4: 实现 API 依赖、schemas、routes、挂载**

Create `backend/app/api/__init__.py` (空文件).

Create `backend/app/api/deps.py`:
```python
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `backend/app/api/schemas.py`:
```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    platform: str
    handle: str
    vertical: str | None = None
    positioning: str | None = None
    objective_weights: dict | None = None
    acceptance_criteria: str | None = None


class AccountListItem(BaseModel):
    id: int
    platform: str
    handle: str
    vertical: str | None
    positioning: str | None
    latest_followers: int | None
    latest_composite_score: float | None
    latest_loop_status: str | None
    source_tier: str | None


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    followers: int | None
    engagement_rate: float | None
    hit_rate: float | None
    conversions: int | None
    source_tier: str


class ContentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic: str | None
    views: int | None
    likes: int | None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    content: str
    status: str


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    content: str
    review_status: str


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    composite_score: float
    breakdown: dict
    created_at: datetime


class LoopRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    diagnosis: str | None
    verify_result: dict
    status: str
    evaluation: EvaluationOut | None
    recommendations: list[RecommendationOut]
    drafts: list[DraftOut]


class AccountDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: str
    handle: str
    vertical: str | None
    positioning: str | None
    objective_weights: dict
    snapshots: list[SnapshotOut]
    content_items: list[ContentItemOut]
    loop_runs: list[LoopRunOut]
```

Create `backend/app/api/routes.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import get_db
from app.models import Account, Evaluation, LoopRun, Snapshot

router = APIRouter()


def _latest(db: Session, model, account_id: int, *order):
    stmt = select(model).where(model.account_id == account_id).order_by(*order)
    return db.scalars(stmt).first()


def _list_item(db: Session, acc: Account) -> schemas.AccountListItem:
    snap = _latest(db, Snapshot, acc.id, Snapshot.ts.desc(), Snapshot.id.desc())
    ev = _latest(db, Evaluation, acc.id, Evaluation.created_at.desc(), Evaluation.id.desc())
    run = _latest(db, LoopRun, acc.id, LoopRun.ts.desc(), LoopRun.id.desc())
    return schemas.AccountListItem(
        id=acc.id,
        platform=acc.platform,
        handle=acc.handle,
        vertical=acc.vertical,
        positioning=acc.positioning,
        latest_followers=snap.followers if snap else None,
        latest_composite_score=ev.composite_score if ev else None,
        latest_loop_status=run.status if run else None,
        source_tier=snap.source_tier if snap else None,
    )


@router.post("/accounts", response_model=schemas.AccountListItem, status_code=201)
def create_account(payload: schemas.AccountCreate, db: Session = Depends(get_db)) -> schemas.AccountListItem:
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    acc = Account(**data)
    db.add(acc)
    db.commit()
    return _list_item(db, acc)


@router.get("/accounts", response_model=list[schemas.AccountListItem])
def list_accounts(db: Session = Depends(get_db)) -> list[schemas.AccountListItem]:
    accounts = db.scalars(select(Account).order_by(Account.id)).all()
    return [_list_item(db, a) for a in accounts]
```

Modify `backend/app/main.py` — add the router import and mount it (keep the existing `/health`):
```python
from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="MatrixLoop")
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_accounts.py tests/test_app.py -v`
Expected: PASS (3 passed — 含原 /health 测试)

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api backend/app/main.py backend/tests/conftest.py backend/tests/test_api_accounts.py
git commit -m "feat(api): FastAPI account create/list with latest metrics + db dependency + schemas"
```

---

### Task 2: 单账号下钻端点

**Files:**
- Modify: `backend/app/api/routes.py` (追加 GET /accounts/{id})
- Test: `backend/tests/test_api_account_detail.py`

- [ ] **Step 1: 写失败的下钻测试**

Create `backend/tests/test_api_account_detail.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation, Recommendation, Draft


def test_account_detail_returns_nested(client, session):
    acc = Account(platform="x", handle="@a3")
    session.add(acc)
    session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=500))
    session.add(ContentItem(account_id=acc.id, topic="ai", views=999))
    run = LoopRun(account_id=acc.id, diagnosis="诊断", status="ok")
    run.evaluation = Evaluation(account_id=acc.id, composite_score=61.0, breakdown={"growth": 61})
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦"))
    run.drafts.append(Draft(kind="topic", content="选题一"))
    session.add(run)
    session.commit()

    resp = client.get(f"/accounts/{acc.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["handle"] == "@a3"
    assert body["snapshots"][0]["followers"] == 500
    assert body["content_items"][0]["topic"] == "ai"
    assert body["loop_runs"][0]["diagnosis"] == "诊断"
    assert body["loop_runs"][0]["evaluation"]["composite_score"] == 61.0
    assert body["loop_runs"][0]["recommendations"][0]["content"] == "聚焦"
    assert body["loop_runs"][0]["drafts"][0]["content"] == "选题一"


def test_account_detail_404(client):
    assert client.get("/accounts/99999").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_account_detail.py -v`
Expected: FAIL - 404 for a real id / route missing (405 or 404 on the detail path)

- [ ] **Step 3: 追加下钻路由**

Append to `backend/app/api/routes.py`:
```python
@router.get("/accounts/{account_id}", response_model=schemas.AccountDetail)
def get_account(account_id: int, db: Session = Depends(get_db)) -> Account:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return acc
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_account_detail.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/tests/test_api_account_detail.py
git commit -m "feat(api): GET /accounts/{id} detail with nested snapshots/content/loop runs"
```

---

### Task 3: CSV 导入 + 触发 Loop

**Files:**
- Modify: `backend/app/api/routes.py` (追加两个 POST)
- Test: `backend/tests/test_api_import_loop.py`

- [ ] **Step 1: 写失败的导入/触发测试**

Create `backend/tests/test_api_import_loop.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot

CSV = """platform,handle,ts,followers,views,engagement_rate,hit_rate,conversions
xiaohongshu,@imp,2026-07-01T00:00:00+00:00,100000,0,0.05,0,0
xiaohongshu,@imp,2026-07-06T00:00:00+00:00,110000,0,0.05,0,0
"""


def test_import_snapshots_endpoint(client, session):
    resp = client.post("/import/snapshots", json={"csv": CSV})
    assert resp.status_code == 200
    assert resp.json() == {"accounts_created": 1, "snapshots_created": 2}
    assert session.query(Account).filter_by(handle="@imp").count() == 1


def test_trigger_loop_endpoint(client, session):
    acc = Account(platform="x", handle="@loop", objective_weights={
        "growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc)
    session.commit()
    session.add_all([
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000),
        Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=110000),
    ])
    session.commit()

    resp = client.post(f"/accounts/{acc.id}/loop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["evaluation"]["composite_score"] == 100.0
    assert len(body["recommendations"]) >= 1


def test_trigger_loop_404(client):
    assert client.post("/accounts/99999/loop").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_import_loop.py -v`
Expected: FAIL - routes missing (404/405)

- [ ] **Step 3: 追加导入与触发路由**

Add to the imports at the top of `backend/app/api/routes.py`:
```python
import io

from app.ingest.manual_import import import_snapshots_csv
from app.loop.engine import run_loop
```

Append to `backend/app/api/routes.py`:
```python
@router.post("/import/snapshots")
def import_snapshots(payload: dict, db: Session = Depends(get_db)) -> dict:
    csv_text = payload.get("csv", "")
    return import_snapshots_csv(db, io.StringIO(csv_text))


@router.post("/accounts/{account_id}/loop", response_model=schemas.LoopRunOut)
def trigger_loop(account_id: int, db: Session = Depends(get_db)) -> LoopRun:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    return run_loop(db, acc)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_import_loop.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/tests/test_api_import_loop.py
git commit -m "feat(api): POST /import/snapshots and POST /accounts/{id}/loop"
```

---

### Task 4: 建议/草稿 采纳-否决端点

**Files:**
- Modify: `backend/app/api/routes.py` (追加两个 POST)
- Test: `backend/tests/test_api_review.py`

- [ ] **Step 1: 写失败的审核测试**

Create `backend/tests/test_api_review.py`:
```python
from app.models import Account, LoopRun, Recommendation, Draft


def _seed_run(session):
    acc = Account(platform="x", handle="@rv")
    session.add(acc)
    session.commit()
    run = LoopRun(account_id=acc.id, status="ok")
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦"))
    run.drafts.append(Draft(kind="topic", content="选题"))
    session.add(run)
    session.commit()
    return run.recommendations[0].id, run.drafts[0].id


def test_adopt_recommendation(client, session):
    rec_id, _ = _seed_run(session)
    resp = client.post(f"/recommendations/{rec_id}/status", json={"status": "adopted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "adopted"


def test_reject_draft(client, session):
    _, draft_id = _seed_run(session)
    resp = client.post(f"/drafts/{draft_id}/status", json={"review_status": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"


def test_invalid_recommendation_status_422(client, session):
    rec_id, _ = _seed_run(session)
    assert client.post(f"/recommendations/{rec_id}/status", json={"status": "bogus"}).status_code == 422


def test_recommendation_404(client):
    assert client.post("/recommendations/99999/status", json={"status": "adopted"}).status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_review.py -v`
Expected: FAIL - routes missing

- [ ] **Step 3: 追加审核路由**

Add `Draft, Recommendation` to the models import at the top of `backend/app/api/routes.py` (it currently imports `Account, Evaluation, LoopRun, Snapshot`):
```python
from app.models import Account, Draft, Evaluation, LoopRun, Recommendation, Snapshot
```

Append to `backend/app/api/routes.py`:
```python
_REC_STATUSES = {"pending", "adopted", "rejected", "worked", "failed"}
_DRAFT_STATUSES = {"pending", "adopted", "rejected"}


@router.post("/recommendations/{rec_id}/status", response_model=schemas.RecommendationOut)
def set_recommendation_status(rec_id: int, payload: dict, db: Session = Depends(get_db)) -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    status = payload.get("status")
    if status not in _REC_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid status; allowed: {sorted(_REC_STATUSES)}")
    rec.status = status
    db.commit()
    return rec


@router.post("/drafts/{draft_id}/status", response_model=schemas.DraftOut)
def set_draft_status(draft_id: int, payload: dict, db: Session = Depends(get_db)) -> Draft:
    draft = db.get(Draft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    review = payload.get("review_status")
    if review not in _DRAFT_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid review_status; allowed: {sorted(_DRAFT_STATUSES)}")
    draft.review_status = review
    db.commit()
    return draft
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_review.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（此前 62 + 本计划 11 = 73 passed）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/tests/test_api_review.py
git commit -m "feat(api): adopt/reject endpoints for recommendations and drafts"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（此前 62 + 本计划 11 = 73）
- REST 面：`POST/GET /accounts`、`GET /accounts/{id}`（下钻）、`POST /import/snapshots`、`POST /accounts/{id}/loop`、`POST /recommendations/{id}/status`、`POST /drafts/{id}/status`
- Dashboard（plan 6）可直接消费这些端点：总览列表 + 下钻 + 待办队列的采纳/否决动作
- 备注：API 触发 Loop 暂走确定性路径（未注入 llm_client）；接 LLM/鉴权/分页留待后续
