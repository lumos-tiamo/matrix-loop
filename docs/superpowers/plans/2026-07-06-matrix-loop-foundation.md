# MatrixLoop 地基（Foundation）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起 MatrixLoop 后端脚手架与数据模型，并支持手动 CSV 导入账号快照，让真实数据能进入系统、被查询和测试。

**Architecture:** Python + FastAPI 应用骨架；SQLAlchemy 2.0 ORM + SQLite（默认，可换 Postgres）；7 张核心表（Account / Snapshot / ContentItem / Evaluation / LoopRun / Recommendation / Draft）；一个 CSV 导入器把快照写入 DB；一个 `/health` 端点让应用可运行。全程 TDD、频繁提交。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic, pytest, uvicorn, SQLite。

**总设计 spec：** `docs/superpowers/specs/2026-07-06-matrix-loop-design.md`（本计划实现其中「数据模型」+「手动导入兜底」两节，是后续所有计划的地基）。

---

### Task 1: 后端脚手架与数据库基座

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: 写依赖清单**

Create `backend/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
SQLAlchemy==2.0.35
pydantic==2.9.2
pydantic-settings==2.5.2
httpx==0.27.2
pytest==8.3.3
```

- [ ] **Step 2: 建 Python 环境并安装依赖**

Run:
```bash
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt && python -c "import fastapi, sqlalchemy; print('ok')"
```
Expected: 打印 `ok`

- [ ] **Step 3: 写包初始化与配置**

Create `backend/app/__init__.py`:
```python
```
(空文件，标记为包)

Create `backend/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATRIXLOOP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/matrixloop.db"


settings = Settings()
```

- [ ] **Step 4: 写失败的 DB 测试**

Create `backend/tests/__init__.py` (空文件).

Create `backend/tests/test_db.py`:
```python
from sqlalchemy import text

from app.db import Base, engine, SessionLocal


def test_engine_connects():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_session_and_base_exist():
    assert Base is not None
    session = SessionLocal()
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        session.close()
```

- [ ] **Step 5: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 6: 实现 db.py**

Create `backend/app/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && mkdir -p data && python -m pytest tests/test_db.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/requirements.txt backend/app backend/tests
git commit -m "feat(backend): scaffold FastAPI app + SQLAlchemy db base"
```

---

### Task 2: Account 与 Snapshot 模型

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_models_account.py`

- [ ] **Step 1: 写测试用的内存 DB fixture**

Create `backend/tests/conftest.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
import app.models  # noqa: F401  确保所有模型已注册到 Base.metadata


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
```

- [ ] **Step 2: 写失败的 Account/Snapshot 测试**

Create `backend/tests/test_models_account.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot


def test_create_account_with_defaults(session):
    acc = Account(platform="xiaohongshu", handle="@a1", vertical="beauty")
    session.add(acc)
    session.commit()
    assert acc.id is not None
    assert acc.objective_weights == {"growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25}


def test_snapshot_linked_to_account(session):
    acc = Account(platform="douyin", handle="@a2")
    session.add(acc)
    session.commit()
    snap = Snapshot(
        account_id=acc.id,
        ts=datetime(2026, 7, 6, tzinfo=timezone.utc),
        followers=1000,
        engagement_rate=0.043,
        source_tier="manual",
    )
    session.add(snap)
    session.commit()
    assert snap.id is not None
    assert acc.snapshots[0].followers == 1000
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_models_account.py -v`
Expected: FAIL - `ImportError: cannot import name 'Account' from 'app.models'`

- [ ] **Step 4: 实现 Account 与 Snapshot 模型**

Create `backend/app/models.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_weights() -> dict:
    return {"growth": 0.25, "engagement": 0.25, "commercial": 0.25, "positioning": 0.25}


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    handle: Mapped[str] = mapped_column(String(128), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), nullable=True)
    positioning: Mapped[str | None] = mapped_column(String, nullable=True)
    objective_weights: Mapped[dict] = mapped_column(JSON, default=_default_weights)
    acceptance_criteria: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_tier: Mapped[str] = mapped_column(String(16), default="manual")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped["Account"] = relationship(back_populates="snapshots")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_models_account.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/conftest.py backend/tests/test_models_account.py
git commit -m "feat(models): Account + Snapshot with objective weights and time-series metrics"
```

---

### Task 3: ContentItem / Evaluation / LoopRun / Recommendation / Draft 模型

**Files:**
- Modify: `backend/app/models.py` (追加 5 个模型)
- Test: `backend/tests/test_models_loop.py`

- [ ] **Step 1: 写失败的关系测试**

Create `backend/tests/test_models_loop.py`:
```python
from app.models import Account, LoopRun, Evaluation, Recommendation, Draft, ContentItem


def test_loop_run_aggregates_children(session):
    acc = Account(platform="x", handle="@a3")
    session.add(acc)
    session.commit()

    run = LoopRun(account_id=acc.id, diagnosis="定位偏散", status="ok", tokens_cost=1234)
    run.evaluation = Evaluation(
        account_id=acc.id,
        composite_score=88.0,
        breakdown={"growth": 90, "engagement": 85, "commercial": 80, "positioning": 95},
    )
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦平价美妆测评", status="pending"))
    run.drafts.append(Draft(kind="topic", content="5款百元粉底横评", review_status="pending"))
    session.add(run)
    session.commit()

    assert run.id is not None
    assert run.evaluation.composite_score == 88.0
    assert run.recommendations[0].status == "pending"
    assert run.drafts[0].review_status == "pending"


def test_content_item_linked_to_account(session):
    acc = Account(platform="tiktok", handle="@a4")
    session.add(acc)
    session.commit()
    ci = ContentItem(account_id=acc.id, platform_post_id="p123", type="video", views=5000, likes=300)
    session.add(ci)
    session.commit()
    assert ci.id is not None
    assert acc.content_items[0].views == 5000
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_models_loop.py -v`
Expected: FAIL - `ImportError: cannot import name 'LoopRun' from 'app.models'`

- [ ] **Step 3: 追加 5 个模型到 models.py**

Append to `backend/app/models.py`:
```python
class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    account: Mapped["Account"] = relationship(back_populates="content_items")


class LoopRun(Base):
    __tablename__ = "loop_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    diagnosis: Mapped[str | None] = mapped_column(String, nullable=True)
    verify_result: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens_cost: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="ok")  # ok|no_progress|error|budget_stop

    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="loop_run", uselist=False, cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="loop_run", cascade="all, delete-orphan"
    )
    drafts: Mapped[list["Draft"]] = relationship(back_populates="loop_run", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    loop_run_id: Mapped[int | None] = mapped_column(ForeignKey("loop_runs.id"), nullable=True)
    composite_score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    loop_run: Mapped["LoopRun | None"] = relationship(back_populates="evaluation")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_run_id: Mapped[int] = mapped_column(ForeignKey("loop_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # positioning|content_direction|cadence
    content: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|worked|failed|rejected

    loop_run: Mapped["LoopRun"] = relationship(back_populates="recommendations")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loop_run_id: Mapped[int] = mapped_column(ForeignKey("loop_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # topic|script
    content: Mapped[str] = mapped_column(String)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|adopted|rejected

    loop_run: Mapped["LoopRun"] = relationship(back_populates="drafts")
```

Also add the `content_items` back-reference to `Account`. Modify the `Account` class in `backend/app/models.py` by adding this relationship right after the existing `snapshots` relationship line:
```python
    content_items: Mapped[list["ContentItem"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: 运行全部模型测试确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_models_account.py tests/test_models_loop.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_loop.py
git commit -m "feat(models): ContentItem, LoopRun, Evaluation, Recommendation, Draft"
```

---

### Task 4: 手动 CSV 快照导入（手动兜底 MVP）

CSV 表头约定：`platform,handle,ts,followers,views,engagement_rate,hit_rate,conversions`。导入器按 `(platform, handle)` 找账号，找不到就新建；每行插入一条 `source_tier="manual"` 的 Snapshot。

**Files:**
- Create: `backend/app/ingest/__init__.py`
- Create: `backend/app/ingest/manual_import.py`
- Test: `backend/tests/test_manual_import.py`

- [ ] **Step 1: 写失败的导入测试**

Create `backend/tests/test_manual_import.py`:
```python
import io

from app.ingest.manual_import import import_snapshots_csv
from app.models import Account, Snapshot

CSV = """platform,handle,ts,followers,views,engagement_rate,hit_rate,conversions
xiaohongshu,@a1,2026-07-06T00:00:00+00:00,88000,120000,0.043,0.15,3
xiaohongshu,@a1,2026-07-05T00:00:00+00:00,86000,110000,0.041,0.12,2
douyin,@a2,2026-07-06T00:00:00+00:00,120000,900000,0.030,0.05,0
"""


def test_import_creates_accounts_and_snapshots(session):
    result = import_snapshots_csv(session, io.StringIO(CSV))
    assert result["accounts_created"] == 2
    assert result["snapshots_created"] == 3

    accounts = session.query(Account).all()
    assert {a.handle for a in accounts} == {"@a1", "@a2"}

    a1 = session.query(Account).filter_by(handle="@a1").one()
    assert len(a1.snapshots) == 2
    latest = max(a1.snapshots, key=lambda s: s.ts)
    assert latest.followers == 88000
    assert latest.source_tier == "manual"


def test_import_reuses_existing_account(session):
    session.add(Account(platform="xiaohongshu", handle="@a1"))
    session.commit()
    result = import_snapshots_csv(session, io.StringIO(CSV))
    assert result["accounts_created"] == 1  # 只新建了 @a2
    assert session.query(Snapshot).count() == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_manual_import.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.ingest'`

- [ ] **Step 3: 实现导入器**

Create `backend/app/ingest/__init__.py` (空文件).

Create `backend/app/ingest/manual_import.py`:
```python
from __future__ import annotations

import csv
from datetime import datetime
from typing import TextIO

from sqlalchemy.orm import Session

from app.models import Account, Snapshot

_INT_FIELDS = ("followers", "views", "conversions")
_FLOAT_FIELDS = ("engagement_rate", "hit_rate")


def _parse_int(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def _parse_float(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def import_snapshots_csv(session: Session, fp: TextIO) -> dict:
    """Import account snapshots from a CSV file object. Returns counts."""
    reader = csv.DictReader(fp)
    accounts_created = 0
    snapshots_created = 0
    cache: dict[tuple[str, str], Account] = {}

    for row in reader:
        platform = row["platform"].strip()
        handle = row["handle"].strip()
        key = (platform, handle)

        account = cache.get(key)
        if account is None:
            account = session.query(Account).filter_by(platform=platform, handle=handle).one_or_none()
            if account is None:
                account = Account(platform=platform, handle=handle)
                session.add(account)
                session.flush()  # 拿到 account.id
                accounts_created += 1
            cache[key] = account

        snapshot = Snapshot(
            account_id=account.id,
            ts=datetime.fromisoformat(row["ts"].strip()),
            source_tier="manual",
            **{f: _parse_int(row.get(f)) for f in _INT_FIELDS},
            **{f: _parse_float(row.get(f)) for f in _FLOAT_FIELDS},
        )
        session.add(snapshot)
        snapshots_created += 1

    session.commit()
    return {"accounts_created": accounts_created, "snapshots_created": snapshots_created}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_manual_import.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/ingest backend/tests/test_manual_import.py
git commit -m "feat(ingest): manual CSV snapshot import (accounts auto-created)"
```

---

### Task 5: 可运行的 FastAPI 应用 + DB 初始化

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/init_db.py`
- Test: `backend/tests/test_app.py`

- [ ] **Step 1: 写失败的应用测试**

Create `backend/tests/test_app.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "matrixloop"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_app.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 实现应用与 DB 初始化脚本**

Create `backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="MatrixLoop")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "matrixloop"}
```

Create `backend/app/init_db.py`:
```python
"""Create all tables against the configured database. Run once to bootstrap."""
from app.db import Base, engine
import app.models  # noqa: F401  注册所有模型


def main() -> None:
    Base.metadata.create_all(engine)
    print(f"tables created: {sorted(Base.metadata.tables)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_app.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 端到端手动验证：建库 + 起服务**

Run:
```bash
cd backend && . .venv/bin/activate && mkdir -p data && python -m app.init_db
```
Expected: 打印 `tables created: ['accounts', 'content_items', 'drafts', 'evaluations', 'loop_runs', 'recommendations', 'snapshots']`

- [ ] **Step 6: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -v`
Expected: PASS (全部 7+ 用例通过)

- [ ] **Step 7: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/main.py backend/app/init_db.py backend/tests/test_app.py
git commit -m "feat(app): runnable FastAPI app with /health + init_db bootstrap"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿
- `python -m app.init_db` 能建出 7 张表
- 能用 `import_snapshots_csv` 把一份 CSV 导入成账号 + 快照
- 后续计划（评估/分析引擎）可直接在这些模型和数据上开工
