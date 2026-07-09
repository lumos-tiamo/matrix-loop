# AiToEarn Ingestion (real-data read side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed the loop real per-account follower/engagement snapshots from three self-built official-API connectors (X exists; YouTube + Instagram new) and from a running AiToEarn service (for xhs/douyin/weixin_video/weixin_gzh/tiktok), with account mapping and graceful manual-CSV fallback.

**Architecture:** matrix-loop stays a pure Python brain. New connectors follow the existing `Connector` pattern (`tier` class attr, injected `http_get`, `fetch(account) -> ConnectorResult`). AiToEarn is reached only over HTTP (`x-api-key`) via a thin client; its analytics VO is mapped into `Snapshot` rows. `resolve_connector` routes each platform to the right connector when its config is present, else returns `(None, "manual")` (CSV fallback). This plan is the READ side only — the publish hand and per-post `ContentItem` ingestion are separate later plans.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, pytest, httpx. Backend Python: `backend/.venv/bin/python`. Run pytest from `backend/`.

**Scope note:** Snapshot-level ingestion only (followers / views / engagement_rate). This is the data that drives the loop's growth/engagement/commercial scores. Per-post `ContentItem` ingestion (YouTube videos, IG media, AiToEarn works) is deliberately deferred to a follow-up plan to keep this one shippable and consistent with the existing connectors (which are all snapshot-only today).

---

## File Structure

- `backend/app/config.py` (modify) — 5 new optional settings.
- `backend/app/models.py` (modify) — `Account.external_ref`, `Account.external_source`.
- `backend/app/connectors/aitoearn_client.py` (create) — thin AiToEarn HTTP client (read methods) + platform-name mapping.
- `backend/app/connectors/aitoearn.py` (create) — `AiToEarnConnector`.
- `backend/app/connectors/youtube.py` (create) — `YouTubeConnector`.
- `backend/app/connectors/instagram.py` (create) — `InstagramConnector`.
- `backend/app/connectors/registry.py` (modify) — routing.
- `backend/app/connectors/linking.py` (create) — `link_aitoearn_accounts`.
- `backend/app/api/routes.py` (modify) — `POST /accounts/{id}/external-ref`, `POST /accounts/link-aitoearn`.
- `backend/app/api/schemas.py` (modify) — `SetExternalRef` body schema.
- Tests: `backend/tests/test_config.py`, `test_models_account.py` (extend), `test_aitoearn_client.py`, `test_connector_aitoearn.py`, `test_connector_youtube.py`, `test_connector_instagram.py`, `test_connector_registry.py` (extend), `test_account_linking.py`.

Preconditions before starting: on branch `main`, working tree clean, `cd /Users/aa00102/matrix-loop && git checkout -b feat/aitoearn-ingestion`. Baseline: `cd backend && ./.venv/bin/python -m pytest -q` → 142 passed. Use git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; end commit messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Config additions

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.config import Settings


def test_new_ingestion_settings_default_none():
    s = Settings()
    assert s.aitoearn_base_url is None
    assert s.aitoearn_api_key is None
    assert s.youtube_api_key is None
    assert s.instagram_token is None
    assert s.instagram_business_id is None


def test_new_ingestion_settings_can_be_set():
    s = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k",
                 youtube_api_key="yt", instagram_token="ig", instagram_business_id="123")
    assert s.aitoearn_base_url == "http://x/api/v2"
    assert s.aitoearn_api_key == "k"
    assert s.youtube_api_key == "yt"
    assert s.instagram_token == "ig"
    assert s.instagram_business_id == "123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL (`Settings` has no `aitoearn_base_url`).

- [ ] **Step 3: Add the fields**

In `backend/app/config.py`, inside `class Settings`, after the existing `scrapecreators_api_key` line, add:

```python
    aitoearn_base_url: str | None = None
    aitoearn_api_key: str | None = None
    youtube_api_key: str | None = None
    instagram_token: str | None = None
    instagram_business_id: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/config.py backend/tests/test_config.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(config): add AiToEarn/YouTube/Instagram ingestion settings\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: `Account.external_ref` + `external_source`

**Files:**
- Modify: `backend/app/models.py:24-33` (Account columns)
- Test: `backend/tests/test_models_account.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models_account.py`:

```python
def test_account_external_ref_defaults_none_and_persists(session):
    from app.models import Account
    a = Account(platform="xiaohongshu", handle="@x")
    session.add(a); session.commit()
    assert a.external_ref is None
    assert a.external_source is None
    a.external_ref = "ae_123"
    a.external_source = "aitoearn"
    session.commit()
    got = session.get(Account, a.id)
    assert got.external_ref == "ae_123"
    assert got.external_source == "aitoearn"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_account.py -q`
Expected: FAIL (`Account` has no attribute `external_ref`).

- [ ] **Step 3: Add the columns**

In `backend/app/models.py`, in `class Account`, after the `endpoint_id` column (line ~32), add:

```python
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    external_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_models_account.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_account.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(models): Account.external_ref + external_source for downstream account mapping\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

Note: the running dev server DB must be recreated for the new columns (`rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`). Not needed for tests (in-memory `create_all`).

---

### Task 3: AiToEarn HTTP client (read methods) + platform mapping

**Files:**
- Create: `backend/app/connectors/aitoearn_client.py`
- Test: `backend/tests/test_aitoearn_client.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.connectors.aitoearn_client import AiToEarnClient, to_aitoearn_platform


def test_platform_mapping():
    assert to_aitoearn_platform("xiaohongshu") == "xhs"
    assert to_aitoearn_platform("weixin_video") == "wxSph"
    assert to_aitoearn_platform("weixin_gzh") == "wxGzh"
    assert to_aitoearn_platform("douyin") == "douyin"
    assert to_aitoearn_platform("unknown") == "unknown"


def test_account_analytics_builds_url_and_auth():
    calls = {}
    def fake_get(url, headers):
        calls["url"] = url; calls["headers"] = headers
        return {"metrics": {"fansCount": 500}}
    c = AiToEarnClient("http://host:8080/api/v2/", "KEY", http_get=fake_get)
    out = c.account_analytics("acc_1")
    assert out == {"metrics": {"fansCount": 500}}
    assert calls["url"] == "http://host:8080/api/v2/channels/accounts/acc_1/analytics"
    assert calls["headers"]["x-api-key"] == "KEY"


def test_list_accounts_filters_types():
    seen = {}
    def fake_get(url, headers):
        seen["url"] = url
        return {"total": 0, "list": []}
    c = AiToEarnClient("http://host/api/v2", "KEY", http_get=fake_get)
    c.list_accounts(types=["xhs", "douyin"])
    assert "types[]=xhs" in seen["url"] and "types[]=douyin" in seen["url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_aitoearn_client.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement the client**

Create `backend/app/connectors/aitoearn_client.py`:

```python
from __future__ import annotations

# matrix-loop platform string -> AiToEarn AccountType
PLATFORM_MAP = {
    "xiaohongshu": "xhs",
    "weixin_video": "wxSph",
    "weixin_gzh": "wxGzh",
    "douyin": "douyin",
    "tiktok": "tiktok",
    "twitter": "twitter",
    "youtube": "youtube",
    "instagram": "instagram",
    "bilibili": "bilibili",
}


def to_aitoearn_platform(platform: str) -> str:
    return PLATFORM_MAP.get(platform, platform)


class AiToEarnClient:
    """Thin HTTP client for AiToEarn's REST API. Injected http_get/http_post for tests."""

    def __init__(self, base_url: str, api_key: str, http_get=None, http_post=None):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self._http_get = http_get or self._default_get
        self._http_post = http_post or self._default_post

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx
        resp = httpx.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx
        resp = httpx.post(url, headers=headers, json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_accounts(self, types: list[str] | None = None) -> dict:
        url = f"{self.base_url}/channels/accounts"
        if types:
            url += "?" + "&".join(f"types[]={t}" for t in types)
        return self._http_get(url, self._headers()) or {}

    def account_analytics(self, account_id: str, since: str | None = None, until: str | None = None) -> dict:
        url = f"{self.base_url}/channels/accounts/{account_id}/analytics"
        qs = [f"{k}={v}" for k, v in (("since", since), ("until", until)) if v]
        if qs:
            url += "?" + "&".join(qs)
        return self._http_get(url, self._headers()) or {}

    def work_analytics(self, platform: str, work_id: str, account_id: str,
                       since: str | None = None, until: str | None = None) -> dict:
        url = f"{self.base_url}/channels/works/{platform}/{work_id}/analytics?accountId={account_id}"
        for k, v in (("since", since), ("until", until)):
            if v:
                url += f"&{k}={v}"
        return self._http_get(url, self._headers()) or {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_aitoearn_client.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/aitoearn_client.py backend/tests/test_aitoearn_client.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): AiToEarn HTTP client (read methods) + platform mapping\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: `AiToEarnConnector` (ingestion)

**Files:**
- Create: `backend/app/connectors/aitoearn.py`
- Test: `backend/tests/test_connector_aitoearn.py` (create)

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.connectors.aitoearn import AiToEarnConnector
from app.connectors.base import ManualOnlyError


class _FakeClient:
    def __init__(self, payload): self._payload = payload
    def account_analytics(self, account_id, since=None, until=None): return self._payload


def _acct(external_ref):
    return type("A", (), {"handle": "@x", "platform": "xiaohongshu", "external_ref": external_ref})()


def test_fetch_maps_account_analytics_to_snapshot():
    client = _FakeClient({"metrics": {"fansCount": 5000, "viewCount": 2000, "engagementCount": 100}})
    conn = AiToEarnConnector(client, "xiaohongshu")
    res = conn.fetch(_acct("ae_1"))
    assert res.tier == "aggregator"
    assert res.snapshots == [{"followers": 5000, "views": 2000, "engagement_rate": 0.05}]


def test_fetch_without_external_ref_raises_manual():
    conn = AiToEarnConnector(_FakeClient({}), "douyin")
    with pytest.raises(ManualOnlyError):
        conn.fetch(_acct(None))


def test_fetch_missing_metrics_yields_empty_snapshots():
    conn = AiToEarnConnector(_FakeClient({"metrics": {}}), "tiktok")
    assert conn.fetch(_acct("ae_2")).snapshots == []


def test_sync_persists_aggregator_snapshot(session):
    from app.models import Account, Snapshot
    from app.connectors.sync import sync_account
    acc = Account(platform="xiaohongshu", handle="@x", external_ref="ae_9")
    session.add(acc); session.commit()
    client = _FakeClient({"metrics": {"fansCount": 8000, "viewCount": 4000, "engagementCount": 200}})
    out = sync_account(session, acc, connector=AiToEarnConnector(client, "xiaohongshu"))
    assert out["tier"] == "aggregator" and out["snapshots_created"] == 1
    snap = session.query(Snapshot).filter_by(account_id=acc.id).one()
    assert snap.followers == 8000 and snap.source_tier == "aggregator" and snap.engagement_rate == 0.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_aitoearn.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement the connector**

Create `backend/app/connectors/aitoearn.py`:

```python
from __future__ import annotations

from app.connectors.base import ConnectorResult, ManualOnlyError


class AiToEarnConnector:
    """Ingest an account's follower/engagement snapshot from AiToEarn's analytics API.

    Requires account.external_ref (the AiToEarn accountId). Snapshot-level only;
    per-post content ingestion is a separate follow-up plan.
    """

    tier = "aggregator"

    def __init__(self, client, platform: str):
        self.client = client
        self.platform = platform

    def fetch(self, account) -> ConnectorResult:
        external_ref = getattr(account, "external_ref", None)
        if not external_ref:
            raise ManualOnlyError(
                f"account {account.handle} 未映射 AiToEarn accountId(external_ref);请先 link 或手动设置"
            )
        data = self.client.account_analytics(external_ref) or {}
        metrics = data.get("metrics") or {}
        followers = metrics.get("fansCount")
        views = metrics.get("viewCount")
        engagement = metrics.get("engagementCount")
        snap: dict = {}
        if followers is not None:
            snap["followers"] = followers
        if views is not None:
            snap["views"] = views
        if engagement is not None and views:
            snap["engagement_rate"] = round(engagement / views, 4)
        snapshots = [snap] if snap else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_aitoearn.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/aitoearn.py backend/tests/test_connector_aitoearn.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): AiToEarnConnector snapshot ingestion (requires external_ref)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: `YouTubeConnector` (self-built, Data API v3)

**Files:**
- Create: `backend/app/connectors/youtube.py`
- Test: `backend/tests/test_connector_youtube.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.connectors.youtube import YouTubeConnector


def _acct(handle="@ninacrypto"):
    return type("A", (), {"handle": handle, "platform": "youtube"})()


def test_fetch_maps_channel_statistics_to_snapshot():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        return {"items": [{"statistics": {"subscriberCount": "12000", "viewCount": "3400000"}}]}
    conn = YouTubeConnector("YT_KEY", http_get=fake_get)
    res = conn.fetch(_acct("@ninacrypto"))
    assert res.tier == "api"
    assert res.snapshots == [{"followers": 12000, "views": 3400000}]
    assert "forHandle=ninacrypto" in captured["url"] and "key=YT_KEY" in captured["url"]


def test_fetch_hidden_subs_or_no_channel_yields_empty():
    conn = YouTubeConnector("K", http_get=lambda url, headers: {"items": []})
    assert conn.fetch(_acct()).snapshots == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_youtube.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement the connector**

Create `backend/app/connectors/youtube.py`:

```python
from __future__ import annotations

from app.connectors.base import ConnectorResult


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class YouTubeConnector:
    """YouTube Data API v3 channel statistics -> follower snapshot. Injected http_get for tests."""

    tier = "api"

    def __init__(self, api_key: str, http_get=None):
        self.api_key = api_key
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx
        resp = httpx.get(url, headers=headers or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = (account.handle or "").lstrip("@")
        if not handle:
            raise ValueError("account.handle is empty")
        url = (
            "https://www.googleapis.com/youtube/v3/channels"
            f"?part=statistics&forHandle={handle}&key={self.api_key}"
        )
        data = self._http_get(url, {}) or {}
        items = data.get("items") or []
        if not items:
            return ConnectorResult(tier=self.tier, snapshots=[])
        stats = items[0].get("statistics") or {}
        followers = _to_int(stats.get("subscriberCount"))
        views = _to_int(stats.get("viewCount"))
        snap: dict = {}
        if followers is not None:
            snap["followers"] = followers
        if views is not None:
            snap["views"] = views
        return ConnectorResult(tier=self.tier, snapshots=[snap] if snap else [])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_youtube.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/youtube.py backend/tests/test_connector_youtube.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): YouTubeConnector (Data API v3 channel snapshot)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 6: `InstagramConnector` (self-built, Graph API business discovery)

**Files:**
- Create: `backend/app/connectors/instagram.py`
- Test: `backend/tests/test_connector_instagram.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.connectors.instagram import InstagramConnector


def _acct(handle="@ninaweb3"):
    return type("A", (), {"handle": handle, "platform": "instagram"})()


def test_fetch_maps_business_discovery_to_snapshot():
    captured = {}
    def fake_get(url, headers):
        captured["url"] = url
        return {"business_discovery": {"followers_count": 8800, "media_count": 120, "id": "1"}}
    conn = InstagramConnector("IG_TOKEN", "ig_biz_1", http_get=fake_get)
    res = conn.fetch(_acct("@ninaweb3"))
    assert res.tier == "api"
    assert res.snapshots == [{"followers": 8800}]
    assert "ig_biz_1" in captured["url"]
    assert "business_discovery.username(ninaweb3)" in captured["url"]
    assert "access_token=IG_TOKEN" in captured["url"]


def test_fetch_no_discovery_yields_empty():
    conn = InstagramConnector("T", "b", http_get=lambda url, headers: {})
    assert conn.fetch(_acct()).snapshots == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_instagram.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement the connector**

Create `backend/app/connectors/instagram.py`:

```python
from __future__ import annotations

from app.connectors.base import ConnectorResult


class InstagramConnector:
    """Instagram Graph API business-discovery -> follower snapshot. Injected http_get for tests.

    Reads another business/creator account's public counts via the caller's own IG
    business account id + a long-lived access token.
    """

    tier = "api"

    def __init__(self, access_token: str, business_id: str, http_get=None):
        self.access_token = access_token
        self.business_id = business_id
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx
        resp = httpx.get(url, headers=headers or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = (account.handle or "").lstrip("@")
        if not handle:
            raise ValueError("account.handle is empty")
        url = (
            f"https://graph.facebook.com/v19.0/{self.business_id}"
            f"?fields=business_discovery.username({handle}){{followers_count,media_count}}"
            f"&access_token={self.access_token}"
        )
        data = self._http_get(url, {}) or {}
        disc = data.get("business_discovery") or {}
        followers = disc.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_instagram.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/instagram.py backend/tests/test_connector_instagram.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): InstagramConnector (Graph API business discovery snapshot)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 7: Registry routing

**Files:**
- Modify: `backend/app/connectors/registry.py`
- Test: `backend/tests/test_connector_registry.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_connector_registry.py`:

```python
def test_youtube_with_key_resolves_api():
    from app.config import Settings
    from app.connectors.youtube import YouTubeConnector
    conn, tier = resolve_connector("youtube", Settings(youtube_api_key="k"))
    assert isinstance(conn, YouTubeConnector) and tier == "api"


def test_instagram_with_token_resolves_api():
    from app.config import Settings
    from app.connectors.instagram import InstagramConnector
    conn, tier = resolve_connector("instagram", Settings(instagram_token="t", instagram_business_id="b"))
    assert isinstance(conn, InstagramConnector) and tier == "api"


def test_cn_platform_with_aitoearn_resolves_aggregator():
    from app.config import Settings
    from app.connectors.aitoearn import AiToEarnConnector
    cfg = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k")
    for platform in ("xiaohongshu", "douyin", "weixin_video", "weixin_gzh", "tiktok"):
        conn, tier = resolve_connector(platform, cfg)
        assert isinstance(conn, AiToEarnConnector) and tier == "aggregator", platform


def test_cn_platform_without_aitoearn_is_manual():
    from app.config import Settings
    conn, tier = resolve_connector("xiaohongshu", Settings())
    assert conn is None and tier == "manual"


def test_tiktok_prefers_aitoearn_over_scrapecreators():
    from app.config import Settings
    from app.connectors.aitoearn import AiToEarnConnector
    cfg = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k", scrapecreators_api_key="s")
    conn, tier = resolve_connector("tiktok", cfg)
    assert isinstance(conn, AiToEarnConnector) and tier == "aggregator"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_registry.py -q`
Expected: FAIL (new routes not wired).

- [ ] **Step 3: Rewrite `resolve_connector`**

Replace the body of `backend/app/connectors/registry.py` with:

```python
from __future__ import annotations

from app.config import settings as default_settings
from app.connectors.aitoearn import AiToEarnConnector
from app.connectors.aitoearn_client import AiToEarnClient
from app.connectors.instagram import InstagramConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector
from app.connectors.x import XConnector
from app.connectors.youtube import YouTubeConnector

# Anti-scraping / browser-login platforms served via a running AiToEarn service.
CN_AGGREGATOR = {"xiaohongshu", "douyin", "weixin_video", "weixin_gzh", "tiktok"}
# Legacy ScrapeCreators fallback (only when nothing better is configured).
SCRAPE_PLATFORMS = {"tiktok", "instagram"}


def resolve_connector(platform: str, cfg=None):
    """Return (connector | None, tier). None connector => manual-only (use CSV import)."""
    cfg = cfg or default_settings
    if platform == "twitter" and cfg.x_bearer_token:
        return XConnector(cfg.x_bearer_token), "api"
    if platform == "youtube" and cfg.youtube_api_key:
        return YouTubeConnector(cfg.youtube_api_key), "api"
    if platform == "instagram" and cfg.instagram_token and cfg.instagram_business_id:
        return InstagramConnector(cfg.instagram_token, cfg.instagram_business_id), "api"
    if platform in CN_AGGREGATOR and cfg.aitoearn_base_url and cfg.aitoearn_api_key:
        client = AiToEarnClient(cfg.aitoearn_base_url, cfg.aitoearn_api_key)
        return AiToEarnConnector(client, platform), "aggregator"
    if platform in SCRAPE_PLATFORMS and cfg.scrapecreators_api_key:
        return ScrapeCreatorsConnector(cfg.scrapecreators_api_key, platform), "scrape"
    return None, "manual"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_connector_registry.py -q`
Expected: PASS (existing 4 + new 5). The existing `test_tiktok_with_key_resolves_scrape` still passes because its `Settings(scrapecreators_api_key="k")` has no AiToEarn config, so it falls through to the scrape branch.

- [ ] **Step 5: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/registry.py backend/tests/test_connector_registry.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(connectors): route youtube/instagram self-built + CN platforms to AiToEarn\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 8: Account linking (`link_aitoearn_accounts` + routes)

**Files:**
- Create: `backend/app/connectors/linking.py`
- Modify: `backend/app/api/schemas.py` (add `SetExternalRef`)
- Modify: `backend/app/api/routes.py` (two routes)
- Test: `backend/tests/test_account_linking.py` (create)

- [ ] **Step 1: Write the failing test**

```python
from app.connectors.linking import link_aitoearn_accounts
from app.models import Account


class _FakeClient:
    def __init__(self, rows): self._rows = rows
    def list_accounts(self, types=None):
        return {"total": len(self._rows), "list": self._rows}


def test_link_matches_by_platform_and_handle(session):
    acc = Account(platform="xiaohongshu", handle="@nina")
    other = Account(platform="douyin", handle="@zoe")
    session.add_all([acc, other]); session.commit()
    client = _FakeClient([
        {"id": "ae_xhs_1", "type": "xhs", "uid": "u1", "nickname": "nina"},
        {"id": "ae_dy_1", "type": "douyin", "uid": "u2", "nickname": "someone-else"},
    ])
    report = link_aitoearn_accounts(session, client)
    session.refresh(acc); session.refresh(other)
    assert acc.external_ref == "ae_xhs_1" and acc.external_source == "aitoearn"
    assert other.external_ref is None                       # nickname didn't match
    assert report["linked"] == 1 and report["unmatched_accounts"] >= 1


def test_link_matches_by_uid_fallback(session):
    acc = Account(platform="tiktok", handle="@u_abc")
    session.add(acc); session.commit()
    client = _FakeClient([{"id": "ae_tt", "type": "tiktok", "uid": "u_abc", "nickname": "Display Name"}])
    link_aitoearn_accounts(session, client)
    session.refresh(acc)
    assert acc.external_ref == "ae_tt"


def test_set_external_ref_route(client, session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc); session.commit()
    resp = client.post(f"/accounts/{acc.id}/external-ref",
                       json={"external_ref": "ae_manual", "external_source": "aitoearn"})
    assert resp.status_code == 200
    session.refresh(acc)
    assert acc.external_ref == "ae_manual"


def test_set_external_ref_404(client):
    assert client.post("/accounts/999/external-ref", json={"external_ref": "x"}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_account_linking.py -q`
Expected: FAIL (module + routes missing).

- [ ] **Step 3: Implement the linking helper**

Create `backend/app/connectors/linking.py`:

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.aitoearn_client import to_aitoearn_platform
from app.models import Account


def _norm(s: str | None) -> str:
    return (s or "").lstrip("@").strip().lower()


def link_aitoearn_accounts(session: Session, client) -> dict:
    """Match AiToEarn accounts to matrix-loop accounts by (platform, handle~nickname|uid),
    filling external_ref/external_source. Idempotent; only fills empty external_ref."""
    rows = (client.list_accounts() or {}).get("list") or []
    # index AiToEarn rows by (type, normalized nickname) and (type, normalized uid)
    by_key: dict[tuple[str, str], str] = {}
    for r in rows:
        rid, rtype = r.get("id"), r.get("type")
        if not rid or not rtype:
            continue
        for field in ("nickname", "uid"):
            key = (rtype, _norm(r.get(field)))
            if key[1]:
                by_key.setdefault(key, rid)

    accounts = list(session.scalars(select(Account)).all())
    linked = 0
    for acc in accounts:
        if acc.external_ref:
            continue
        ae_type = to_aitoearn_platform(acc.platform)
        rid = by_key.get((ae_type, _norm(acc.handle)))
        if rid:
            acc.external_ref = rid
            acc.external_source = "aitoearn"
            linked += 1
    session.commit()
    unmatched = sum(1 for a in accounts if not a.external_ref)
    return {"linked": linked, "unmatched_accounts": unmatched, "aitoearn_accounts": len(rows)}
```

- [ ] **Step 4: Add the request schema**

In `backend/app/api/schemas.py`, add (near the other small request models):

```python
class SetExternalRef(BaseModel):
    external_ref: str
    external_source: str | None = "aitoearn"
```

(`BaseModel` is already imported in `schemas.py`.)

- [ ] **Step 5: Add the routes**

In `backend/app/api/routes.py`, add near the other `/accounts/{account_id}/...` routes:

```python
@router.post("/accounts/{account_id}/external-ref")
def set_external_ref(account_id: int, payload: schemas.SetExternalRef, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc.external_ref = payload.external_ref
    acc.external_source = payload.external_source
    db.commit()
    return {"account_id": account_id, "external_ref": acc.external_ref, "external_source": acc.external_source}


@router.post("/accounts/link-aitoearn")
def link_aitoearn(db: Session = Depends(get_db)) -> dict:
    from app.config import settings
    if not (settings.aitoearn_base_url and settings.aitoearn_api_key):
        raise HTTPException(status_code=422, detail="AiToEarn 未配置(MATRIXLOOP_AITOEARN_BASE_URL/API_KEY)")
    from app.connectors.aitoearn_client import AiToEarnClient
    from app.connectors.linking import link_aitoearn_accounts
    client = AiToEarnClient(settings.aitoearn_base_url, settings.aitoearn_api_key)
    return link_aitoearn_accounts(db, client)
```

(`Account`, `HTTPException`, `Depends`, `Session`, `get_db`, `schemas` are already imported in `routes.py`.)

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_account_linking.py -q`
Expected: PASS (4 tests).

- [ ] **Step 7: Full suite regression**

Run: `cd backend && ./.venv/bin/python -m pytest -q`
Expected: all pass (142 baseline + new tests from Tasks 1-8).

- [ ] **Step 8: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add backend/app/connectors/linking.py backend/app/api/schemas.py backend/app/api/routes.py backend/tests/test_account_linking.py
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(api): link_aitoearn_accounts + POST /accounts/{id}/external-ref + /accounts/link-aitoearn\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Dispatch a final code review over the branch diff (`git diff main..HEAD`).
- Recreate the dev DB for the new `Account` columns before restarting the server: `rm -f backend/data/matrixloop.db && cd backend && ./.venv/bin/python seed_demo.py`.
- Use `superpowers:finishing-a-development-branch` to merge to `main` (option 1, `--no-ff`).
- Live smoke (manual, out of suite, gated on a running AiToEarn + connected accounts / real YT/IG tokens): configure `.env`, `POST /accounts/link-aitoearn`, then `POST /accounts/{id}/sync` on a mapped account and confirm a real snapshot lands.

## Self-review notes (against the spec, read side only)

- **Spec coverage:** config (Task 1), AiToEarn client read methods + platform map (Task 3), AiToEarnConnector (Task 4), YouTube (Task 5) + Instagram (Task 6) self-built, account mapping `external_ref` + `link_aitoearn_accounts` + manual override (Tasks 2, 8), registry routing (Task 7). Deferred to later plans (documented): publish hand, per-post `ContentItem` ingestion, close-the-loop, frontend UI.
- **Type consistency:** `resolve_connector -> (connector, tier)` preserved; `ConnectorResult(tier, snapshots, ...)` used uniformly; snapshot dict keys (`followers`/`views`/`engagement_rate`) match `Snapshot` columns filtered by `sync_account._cols`; `AiToEarnClient` method names match connector + linking usage.
- **No placeholders:** every step has full code + exact run commands + expected outcomes.
