# MatrixLoop 连接器（数据接入）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建可插拔连接器框架，把各平台数据归一化成 Snapshot/ContentItem 并入库；实现能自动的真连接器（X API、ScrapeCreators），反爬严的平台标为 manual（走已有 CSV 导入兜底）。每个平台一个「档位」（api/scrape/manual），随时可升级。

**Architecture:** `app/connectors/base.py`（`Connector` Protocol、`ConnectorResult`、`ManualOnlyError`）。`registry.resolve_connector(platform, cfg)` 按平台 + 配置返回 `(connector | None, tier)`：twitter+token→XConnector/api，tiktok|instagram+key→ScrapeCreatorsConnector/scrape，其余→None/manual。`sync.sync_account(session, account, connector=None)` 用连接器抓取、归一化、持久化（source_tier 来自档位），manual 平台抛 `ManualOnlyError`（提示用 CSV 导入）。真连接器把 HTTP 调用做成注入的 `http_get` 可调用对象 → 用假响应测试，绝不打真网。API 加 `POST /accounts/{id}/sync` 触发同步。

**Tech Stack:** Python 3.13（同一 venv），httpx（已在 requirements）、pytest。无新依赖。

**依赖：** 地基 models、plan 5 API、`app/config.py`（前缀 MATRIXLOOP_）。诚实边界：小红书/抖音/视频号/公众号 v1 = manual；X = api（需 `MATRIXLOOP_X_BEARER_TOKEN`）；tiktok/instagram = scrape（需 `MATRIXLOOP_SCRAPECREATORS_API_KEY`）。

---

### Task 1: 连接器基座 + 注册表 + 配置

**Files:**
- Create: `backend/app/connectors/__init__.py`, `backend/app/connectors/base.py`, `backend/app/connectors/registry.py`
- Modify: `backend/app/config.py` (追加 2 个 key)
- Test: `backend/tests/test_connector_registry.py`

- [ ] **Step 1: 追加配置键**

Modify `backend/app/config.py` — add inside `Settings` (after `llm_model`):
```python
    x_bearer_token: str | None = None
    scrapecreators_api_key: str | None = None
```

- [ ] **Step 2: 写失败的注册表测试**

Create `backend/tests/test_connector_registry.py`:
```python
from app.config import Settings
from app.connectors.registry import resolve_connector
from app.connectors.x import XConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector


def test_twitter_with_token_resolves_api():
    cfg = Settings(x_bearer_token="tok")
    conn, tier = resolve_connector("twitter", cfg)
    assert isinstance(conn, XConnector)
    assert tier == "api"


def test_twitter_without_token_is_manual():
    cfg = Settings(x_bearer_token=None)
    conn, tier = resolve_connector("twitter", cfg)
    assert conn is None
    assert tier == "manual"


def test_tiktok_with_key_resolves_scrape():
    cfg = Settings(scrapecreators_api_key="k")
    conn, tier = resolve_connector("tiktok", cfg)
    assert isinstance(conn, ScrapeCreatorsConnector)
    assert tier == "scrape"


def test_xiaohongshu_is_manual():
    conn, tier = resolve_connector("xiaohongshu", Settings())
    assert conn is None
    assert tier == "manual"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connector_registry.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.connectors'`

- [ ] **Step 4: 实现 base + registry**

Create `backend/app/connectors/__init__.py` (空文件).

Create `backend/app/connectors/base.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ConnectorResult:
    tier: str                                   # api | scrape | manual
    snapshots: list[dict] = field(default_factory=list)
    content: list[dict] = field(default_factory=list)


class Connector(Protocol):
    tier: str
    def fetch(self, account) -> ConnectorResult: ...


class ManualOnlyError(RuntimeError):
    """Raised when a platform has no automated connector; use CSV import instead."""
```

Create `backend/app/connectors/registry.py`:
```python
from __future__ import annotations

from app.config import settings as default_settings
from app.connectors.scrapecreators import ScrapeCreatorsConnector
from app.connectors.x import XConnector

SCRAPE_PLATFORMS = {"tiktok", "instagram"}


def resolve_connector(platform: str, cfg=None):
    """Return (connector | None, tier). None connector => manual-only (use CSV import)."""
    cfg = cfg or default_settings
    if platform == "twitter" and cfg.x_bearer_token:
        return XConnector(cfg.x_bearer_token), "api"
    if platform in SCRAPE_PLATFORMS and cfg.scrapecreators_api_key:
        return ScrapeCreatorsConnector(cfg.scrapecreators_api_key, platform), "scrape"
    return None, "manual"
```

Note: `registry.py` imports `XConnector`/`ScrapeCreatorsConnector` from Task 3's modules. Create minimal placeholders now so Task 1 runs; Task 3 fills them:

Create `backend/app/connectors/x.py`:
```python
class XConnector:
    tier = "api"
    def __init__(self, bearer_token, http_get=None):
        self.bearer_token = bearer_token
        self._http_get = http_get
```

Create `backend/app/connectors/scrapecreators.py`:
```python
class ScrapeCreatorsConnector:
    tier = "scrape"
    def __init__(self, api_key, platform, http_get=None):
        self.api_key = api_key
        self.platform = platform
        self._http_get = http_get
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connector_registry.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors backend/app/config.py backend/tests/test_connector_registry.py
git commit -m "feat(connectors): base protocol + result + registry (platform->connector+tier) + config"
```

---

### Task 2: sync_account 持久化

**Files:**
- Create: `backend/app/connectors/sync.py`
- Test: `backend/tests/test_connector_sync.py`

- [ ] **Step 1: 写失败的 sync 测试**

Create `backend/tests/test_connector_sync.py`:
```python
import pytest

from app.models import Account, Snapshot, ContentItem
from app.connectors.base import ConnectorResult, ManualOnlyError
from app.connectors.sync import sync_account


class FakeConnector:
    tier = "api"
    def fetch(self, account):
        return ConnectorResult(
            tier="api",
            snapshots=[{"followers": 1234, "engagement_rate": 0.04}],
            content=[{"platform_post_id": "p1", "topic": "beauty", "views": 500}],
        )


def test_sync_persists_snapshot_and_content_with_tier(session):
    acc = Account(platform="twitter", handle="@a")
    session.add(acc)
    session.commit()

    result = sync_account(session, acc, connector=FakeConnector())
    assert result == {"snapshots_created": 1, "content_created": 1, "tier": "api"}

    snap = session.query(Snapshot).filter_by(account_id=acc.id).one()
    assert snap.followers == 1234
    assert snap.source_tier == "api"
    assert session.query(ContentItem).filter_by(account_id=acc.id).one().topic == "beauty"


def test_sync_manual_platform_raises(session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc)
    session.commit()
    with pytest.raises(ManualOnlyError):
        sync_account(session, acc)  # no connector, resolves to manual
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connector_sync.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.connectors.sync'`

- [ ] **Step 3: 实现 sync_account**

Create `backend/app/connectors/sync.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.base import ManualOnlyError
from app.connectors.registry import resolve_connector
from app.models import ContentItem, Snapshot


def sync_account(session: Session, account, *, connector=None, cfg=None) -> dict:
    if connector is None:
        connector, _tier = resolve_connector(account.platform, cfg)
        if connector is None:
            raise ManualOnlyError(f"{account.platform} 无自动连接器，请用 CSV 导入")

    result = connector.fetch(account)
    now = datetime.now(timezone.utc)
    snaps = content = 0
    try:
        for s in result.snapshots:
            session.add(Snapshot(account_id=account.id, ts=now, source_tier=result.tier, **s))
            snaps += 1
        for c in result.content:
            session.add(ContentItem(account_id=account.id, **c))
            content += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"snapshots_created": snaps, "content_created": content, "tier": result.tier}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connector_sync.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/sync.py backend/tests/test_connector_sync.py
git commit -m "feat(connectors): sync_account persists normalized snapshots/content with tier + rollback guard"
```

---

### Task 3: 真连接器（X API + ScrapeCreators，注入 HTTP）

**Files:**
- Rewrite: `backend/app/connectors/x.py`, `backend/app/connectors/scrapecreators.py`
- Test: `backend/tests/test_connectors_http.py`

- [ ] **Step 1: 写失败的连接器解析测试**

Create `backend/tests/test_connectors_http.py`:
```python
from app.models import Account
from app.connectors.x import XConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector


def test_x_connector_parses_public_metrics():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        captured["headers"] = headers
        return {"data": {"username": "a", "public_metrics": {"followers_count": 9001, "tweet_count": 42}}}

    conn = XConnector("BEARER", http_get=fake_get)
    result = conn.fetch(Account(platform="twitter", handle="@a"))
    assert result.tier == "api"
    assert result.snapshots == [{"followers": 9001}]
    assert "by/username/a" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer BEARER"


def test_scrapecreators_connector_parses_followers():
    def fake_get(url, headers):
        assert headers["x-api-key"] == "KEY"
        return {"followers": 55000}

    conn = ScrapeCreatorsConnector("KEY", "tiktok", http_get=fake_get)
    result = conn.fetch(Account(platform="tiktok", handle="@b"))
    assert result.tier == "scrape"
    assert result.snapshots == [{"followers": 55000}]


def test_x_connector_handles_missing_metrics():
    conn = XConnector("t", http_get=lambda url, headers: {"data": {}})
    result = conn.fetch(Account(platform="twitter", handle="@c"))
    assert result.snapshots == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connectors_http.py -v`
Expected: FAIL - `AttributeError: 'XConnector' object has no attribute 'fetch'`

- [ ] **Step 3: 实现真连接器**

Rewrite `backend/app/connectors/x.py`:
```python
from __future__ import annotations

from app.connectors.base import ConnectorResult


class XConnector:
    """X (Twitter) API v2 user lookup -> follower snapshot. Injected http_get for tests."""

    tier = "api"

    def __init__(self, bearer_token: str, http_get=None):
        self.bearer_token = bearer_token
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = account.handle.lstrip("@")
        url = f"https://api.twitter.com/2/users/by/username/{handle}?user.fields=public_metrics"
        data = self._http_get(url, {"Authorization": f"Bearer {self.bearer_token}"})
        metrics = ((data or {}).get("data") or {}).get("public_metrics") or {}
        followers = metrics.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
```

Rewrite `backend/app/connectors/scrapecreators.py`:
```python
from __future__ import annotations

from app.connectors.base import ConnectorResult


class ScrapeCreatorsConnector:
    """ScrapeCreators profile lookup for tiktok/instagram -> follower snapshot. Injected http_get for tests."""

    tier = "scrape"

    def __init__(self, api_key: str, platform: str, http_get=None):
        self.api_key = api_key
        self.platform = platform
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = account.handle.lstrip("@")
        url = f"https://api.scrapecreators.com/v1/{self.platform}/profile?handle={handle}"
        data = self._http_get(url, {"x-api-key": self.api_key}) or {}
        followers = data.get("followers") if data.get("followers") is not None else data.get("follower_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_connectors_http.py tests/test_connector_registry.py -v`
Expected: PASS (7 passed — 含 registry 4 仍绿)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/x.py backend/app/connectors/scrapecreators.py backend/tests/test_connectors_http.py
git commit -m "feat(connectors): X API v2 + ScrapeCreators connectors over injected http client"
```

---

### Task 4: API 端点 POST /accounts/{id}/sync

**Files:**
- Modify: `backend/app/api/routes.py` (追加 sync 路由)
- Test: `backend/tests/test_api_sync.py`

- [ ] **Step 1: 写失败的 sync 端点测试**

Create `backend/tests/test_api_sync.py`:
```python
import app.api.routes as routes
from app.models import Account
from app.connectors.base import ConnectorResult


def test_sync_manual_platform_returns_422(client, session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc)
    session.commit()
    resp = client.post(f"/accounts/{acc.id}/sync")
    assert resp.status_code == 422


def test_sync_happy_path(client, session, monkeypatch):
    acc = Account(platform="twitter", handle="@a")
    session.add(acc)
    session.commit()

    class FakeConnector:
        tier = "api"
        def fetch(self, account):
            return ConnectorResult(tier="api", snapshots=[{"followers": 777}], content=[])

    monkeypatch.setattr(routes, "resolve_connector", lambda platform, cfg=None: (FakeConnector(), "api"))
    resp = client.post(f"/accounts/{acc.id}/sync")
    assert resp.status_code == 200
    assert resp.json()["snapshots_created"] == 1
    assert resp.json()["tier"] == "api"


def test_sync_404(client):
    assert client.post("/accounts/99999/sync").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_sync.py -v`
Expected: FAIL - 404/405 (route missing)

- [ ] **Step 3: 追加 sync 路由**

Add to the top imports of `backend/app/api/routes.py`:
```python
from app.connectors.base import ManualOnlyError
from app.connectors.registry import resolve_connector
from app.connectors.sync import sync_account
```

Append to `backend/app/api/routes.py`:
```python
@router.post("/accounts/{account_id}/sync")
def sync_account_endpoint(account_id: int, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    connector, tier = resolve_connector(acc.platform)
    if connector is None:
        raise HTTPException(status_code=422, detail=f"{acc.platform} 无自动连接器（档位 {tier}）；请用 CSV 导入")
    try:
        return sync_account(db, acc, connector=connector)
    except ManualOnlyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"connector sync failed: {exc}") from exc
```

Note: the test monkeypatches `routes.resolve_connector`, so the route MUST call the module-level `resolve_connector` name (imported above) rather than reaching through another module.

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && . .venv/bin/activate && python -m pytest tests/test_api_sync.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 跑全部测试**

Run: `cd backend && . .venv/bin/activate && python -m pytest -q`
Expected: PASS（此前 76 + 本计划 12 = 88 passed）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/tests/test_api_sync.py
git commit -m "feat(api): POST /accounts/{id}/sync triggers connector; 422 manual-only, 502 on connector error"
```

---

## 完成标准（本计划）

- `python -m pytest` 全绿（此前 76 + 本计划 12 = 88）
- 连接器框架：`resolve_connector(platform)` 按配置返回连接器 + 档位；`sync_account` 归一化入库并标 source_tier；manual 平台走 `ManualOnlyError`
- 真连接器：`XConnector`（X API v2）、`ScrapeCreatorsConnector`（tiktok/instagram），HTTP 注入、假响应测试、缺 token/key 自动降级 manual
- API：`POST /accounts/{id}/sync`（422 manual-only、404、502 连接器错误）
- 诚实边界：小红书/抖音/视频号/公众号 v1 = manual（CSV 兜底），随 token/key 或后续爬虫升级；真网调用未在测试中触发
- 备注（plan 8）：调度层批量对可自动的账号定时 sync，再 run_loop
