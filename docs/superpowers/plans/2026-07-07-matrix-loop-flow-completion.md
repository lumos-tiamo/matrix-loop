# Flow Completion (导流补全 + 配置端点 + 测试) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining deferred TODOs from the Sankey/flow work: list routes for segments & endpoints, a real demo-reset endpoint, connector bio-link → endpoint auto-match, and wire the frontend flow config to use them, plus edge-case test coverage.

**Architecture:** Additive backend routes (`GET /segments`, `GET /endpoints`, `POST /demo/reset`) reuse existing models and the demo dataset factored out of `seed_demo.py`. `sync_account` gains bio-link auto-match by having `ConnectorResult` carry an optional `bio_url` that the X connector populates from the API, then matching it against endpoints (only when the account has no endpoint yet — never overrides manual). Frontend `FlowConfig` fetches the real segment/endpoint pools on mount and calls the new reset route.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest (backend); Vite + React + TS, vitest + @testing-library/react (frontend).

---

## Backend

### Task 1: `GET /segments` and `GET /endpoints` list routes

**Files:**
- Modify: `backend/app/api/routes.py` (add two GET routes near the existing POST /segments, POST /endpoints)
- Test: `backend/tests/test_flow_api.py` (extend; create if only flow tests live elsewhere — check `backend/tests/` first)

- [ ] **Step 1: Write the failing test**

Add to the flow API test module (the one that already exercises `POST /segments`; if none, create `backend/tests/test_flow_config_api.py` with the standard `client`/`session` fixtures used by other API tests):

```python
def test_list_segments_returns_created(client):
    client.post("/segments", json={"label": "crypto"})
    client.post("/segments", json={"label": "宝妈"})
    resp = client.get("/segments")
    assert resp.status_code == 200
    labels = {s["label"] for s in resp.json()}
    assert {"crypto", "宝妈"} <= labels
    assert all("id" in s and "label" in s for s in resp.json())


def test_list_endpoints_returns_created(client):
    client.post("/endpoints", json={"name": "Nina", "url_pattern": "linktr.ee/nina"})
    resp = client.get("/endpoints")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["name"] == "Nina" and r["url_pattern"] == "linktr.ee/nina" for r in rows)
    assert all({"id", "name", "url_pattern"} <= set(r) for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_flow_config_api.py -q` (from `backend/`)
Expected: FAIL (404 — routes not defined)

- [ ] **Step 3: Implement the routes**

In `backend/app/api/routes.py`, add after the existing `create_segment` / `create_endpoint`:

```python
@router.get("/segments")
def list_segments(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AudienceSegment).order_by(AudienceSegment.label)).all()
    return [{"id": s.id, "label": s.label} for s in rows]


@router.get("/endpoints")
def list_endpoints(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Endpoint).order_by(Endpoint.name)).all()
    return [{"id": e.id, "name": e.name, "url_pattern": e.url_pattern} for e in rows]
```

`select`, `AudienceSegment`, `Endpoint`, `Session`, `Depends`, `get_db` are already imported in this file (used by `create_segment`/`create_endpoint`/`flow`). Verify before adding; do not add duplicate imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_flow_config_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_flow_config_api.py
git commit -m "feat(api): GET /segments + GET /endpoints list routes"
```

---

### Task 2: Extract demo dataset + `POST /demo/reset`

The demo endpoints/segments/assignments currently live as module constants in `seed_demo.py` (`DEMO_ENDPOINTS`, `DEMO_SEGMENTS`, `DEMO_ASSIGN`) and are applied by `seed_flow(db)`. To reset flow wiring from the API without duplicating that data, move the flow-seed logic into an importable helper and have both `seed_demo.py` and the new route call it.

**Files:**
- Create: `backend/app/flow/demo.py` (importable flow-demo constants + `reset_flow(session)`)
- Modify: `backend/seed_demo.py` (import from `app.flow.demo` instead of local constants; keep behavior identical)
- Modify: `backend/app/api/routes.py` (add `POST /demo/reset`)
- Test: `backend/tests/test_flow_config_api.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
def test_demo_reset_wires_flow_for_existing_accounts(client, session):
    from app.models import Account, Snapshot
    from datetime import datetime, timezone
    # accounts must exist first — reset only wires flow onto known handles
    for h in ("@money_talk", "@tech_daily"):
        acc = Account(platform="twitter", handle=h,
                      objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
        session.add(acc); session.commit()
        session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000))
        session.commit()

    resp = client.post("/demo/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoints"] >= 1 and body["segments"] >= 1

    # /flow now has audience + endpoint nodes wired to the seeded handles
    flow = client.get("/flow").json()
    names = {n["name"] for n in flow["nodes"]}
    assert any(n.startswith("seg:") for n in names)
    assert any(n.startswith("ep:") for n in names)


def test_demo_reset_is_idempotent(client, session):
    from app.models import Account, Snapshot
    from datetime import datetime, timezone
    acc = Account(platform="twitter", handle="@money_talk",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=1000))
    session.commit()

    first = client.post("/demo/reset").json()
    second = client.post("/demo/reset").json()
    # running twice must not create duplicate segments/endpoints
    assert first["endpoints"] == second["endpoints"]
    assert first["segments"] == second["segments"]
    segs = client.get("/segments").json()
    assert len({s["label"] for s in segs}) == len(segs)  # no dup labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_flow_config_api.py -q`
Expected: FAIL (404 on `/demo/reset`)

- [ ] **Step 3: Create `backend/app/flow/demo.py`**

```python
"""Demo flow dataset (endpoints / audience segments / account routing) + reset helper.

Single source of truth shared by seed_demo.py and POST /demo/reset. reset_flow is
idempotent: existing segments/endpoints are reused by label/name (no duplicates),
and each named account's composition is fully replaced with the demo wiring.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountSegment, AudienceSegment, Endpoint

# 变现出口 (endpoint name -> bio 外链子串 for auto-match)
DEMO_ENDPOINTS: list[tuple[str, str | None]] = [
    ("Nina", "linktr.ee/nina"),
    ("xaue", "xaue.com"),
    ("私域社群", "t.me/matrixloop"),
]
# 人群标签 (audience segments)
DEMO_SEGMENTS: list[str] = ["crypto", "海外投资者", "宝妈", "打工人群"]
# 账号 -> (出口名 or None=未定向, [(人群标签, 占比), ...])
DEMO_ASSIGN: dict[str, tuple[str | None, list[tuple[str, float]]]] = {
    "@money_talk": ("Nina", [("crypto", 0.6), ("海外投资者", 0.4)]),
    "@tech_daily": ("xaue", [("crypto", 0.5), ("打工人群", 0.5)]),
    "@beauty_lab": ("私域社群", [("宝妈", 0.7), ("打工人群", 0.3)]),
    "@travel_vlog": (None, [("海外投资者", 0.4), ("打工人群", 0.6)]),
    "@fit_coach": ("私域社群", [("打工人群", 1.0)]),
}


def reset_flow(session: Session) -> dict:
    """Idempotently (re)apply the demo flow wiring. Returns counts. Safe to call repeatedly.

    Endpoints/segments are upserted by natural key (name / label). Compositions for the
    named demo handles are fully replaced; accounts absent from the DB are skipped.
    """
    endpoints: dict[str, Endpoint] = {}
    for name, pat in DEMO_ENDPOINTS:
        ep = session.scalar(select(Endpoint).where(Endpoint.name == name))
        if ep is None:
            ep = Endpoint(name=name, url_pattern=pat)
            session.add(ep)
        else:
            ep.url_pattern = pat
        endpoints[name] = ep

    segments: dict[str, AudienceSegment] = {}
    for label in DEMO_SEGMENTS:
        seg = session.scalar(select(AudienceSegment).where(AudienceSegment.label == label))
        if seg is None:
            seg = AudienceSegment(label=label)
            session.add(seg)
        segments[label] = seg
    session.flush()  # assign ids before wiring

    accounts = {a.handle: a for a in session.scalars(select(Account)).all()}
    routed = 0
    for handle, (ep_name, comps) in DEMO_ASSIGN.items():
        acc = accounts.get(handle)
        if acc is None:
            continue
        acc.endpoint_id = endpoints[ep_name].id if ep_name else None
        session.query(AccountSegment).filter_by(account_id=acc.id).delete()
        for label, weight in comps:
            session.add(AccountSegment(account_id=acc.id, segment_id=segments[label].id, weight=weight))
        routed += 1
    session.commit()
    return {"endpoints": len(endpoints), "segments": len(segments), "routed": routed}
```

- [ ] **Step 4: Add `POST /demo/reset` to `backend/app/api/routes.py`**

```python
@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)) -> dict:
    from app.flow.demo import reset_flow
    return reset_flow(db)
```

- [ ] **Step 5: Refactor `seed_demo.py` to use the shared dataset**

In `backend/seed_demo.py`: delete the local `DEMO_ENDPOINTS`, `DEMO_SEGMENTS`, `DEMO_ASSIGN` constants and the body of `seed_flow` that duplicates them. Keep `seed_flow(db)` as a thin wrapper preserving the existing "only seed once" guard and print output:

```python
from app.flow.demo import reset_flow


def seed_flow(db) -> None:
    """Seed endpoints / audience segments / account compositions for the /flow sankey.

    Guarded: only runs the first time (no Endpoint rows yet), so re-running the seeder
    stays idempotent and cheap.
    """
    if db.query(Endpoint).count() > 0:
        print("flow already seeded; skipping")
        return
    counts = reset_flow(db)
    print(f"seeded flow: {counts['endpoints']} endpoints, {counts['segments']} segments, {counts['routed']} accounts routed")
```

Leave the rest of `seed_demo.py` (account/snapshot/content/loop seeding) unchanged. Keep the `Endpoint` import (still used by the guard).

- [ ] **Step 6: Run tests to verify they pass + seeder still works**

Run: `./.venv/bin/python -m pytest tests/test_flow_config_api.py -q`
Expected: PASS

Run (regression — seeder against a fresh DB): `rm -f data/test_seed.db && MATRIXLOOP_DATABASE_URL="sqlite:///./data/test_seed.db" ./.venv/bin/python seed_demo.py`
Expected: prints "seeded N accounts" then "seeded flow: 3 endpoints, 4 segments, 5 accounts routed"; then `rm -f data/test_seed.db`

- [ ] **Step 7: Commit**

```bash
git add backend/app/flow/demo.py backend/seed_demo.py backend/app/api/routes.py backend/tests/test_flow_config_api.py
git commit -m "feat(flow): shared demo dataset + idempotent POST /demo/reset"
```

---

### Task 3: Connector bio-link → endpoint auto-match

**Files:**
- Modify: `backend/app/connectors/base.py` (add `bio_url` to `ConnectorResult`)
- Modify: `backend/app/connectors/x.py` (fetch + extract bio url from X API)
- Modify: `backend/app/connectors/sync.py` (auto-match endpoint when unset)
- Test: `backend/tests/test_connector_sync.py` (extend; the module with existing `sync_account` tests — verify name first)

- [ ] **Step 1: Write the failing tests**

Add to the connector-sync test module (uses a fake connector + in-memory session; mirror existing sync tests' fixtures):

```python
from app.connectors.base import ConnectorResult
from app.connectors.sync import sync_account
from app.models import Account, Endpoint


class _FakeConnector:
    tier = "api"
    def __init__(self, result): self._result = result
    def fetch(self, account): return self._result


def test_sync_auto_matches_endpoint_from_bio_url(session):
    ep = Endpoint(name="Nina", url_pattern="linktr.ee/nina")
    session.add(ep)
    acc = Account(platform="twitter", handle="@x",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add_all([ep, acc]); session.commit()

    conn = _FakeConnector(ConnectorResult(tier="api", snapshots=[{"followers": 100}],
                                          bio_url="https://linktr.ee/nina?ref=x"))
    out = sync_account(session, acc, connector=conn)
    session.refresh(acc)
    assert acc.endpoint_id == ep.id
    assert out.get("endpoint_matched") == "Nina"


def test_sync_does_not_override_existing_endpoint(session):
    a = Endpoint(name="A", url_pattern="a.com"); b = Endpoint(name="B", url_pattern="linktr.ee/nina")
    acc = Account(platform="twitter", handle="@y",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add_all([a, b, acc]); session.commit()
    acc.endpoint_id = a.id; session.commit()

    conn = _FakeConnector(ConnectorResult(tier="api", snapshots=[], bio_url="https://linktr.ee/nina"))
    out = sync_account(session, acc, connector=conn)
    session.refresh(acc)
    assert acc.endpoint_id == a.id            # manual/prior wiring preserved
    assert out.get("endpoint_matched") is None


def test_sync_no_bio_url_is_noop_for_endpoint(session):
    acc = Account(platform="twitter", handle="@z",
                  objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(acc); session.commit()
    conn = _FakeConnector(ConnectorResult(tier="api", snapshots=[{"followers": 5}]))
    out = sync_account(session, acc, connector=conn)
    session.refresh(acc)
    assert acc.endpoint_id is None
    assert out.get("endpoint_matched") is None
```

And an X-connector extraction test in the X connector test module (uses injected `http_get`):

```python
def test_x_connector_extracts_bio_url_from_entities():
    from app.connectors.x import XConnector
    payload = {"data": {"public_metrics": {"followers_count": 1234},
                        "entities": {"url": {"urls": [{"expanded_url": "https://linktr.ee/nina"}]}}}}
    conn = XConnector("tok", http_get=lambda url, headers: payload)
    res = conn.fetch(type("A", (), {"handle": "@nina"})())
    assert res.snapshots == [{"followers": 1234}]
    assert res.bio_url == "https://linktr.ee/nina"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_connector_sync.py tests/test_connector_x.py -q` (adjust filenames to the actual modules)
Expected: FAIL (`ConnectorResult` has no `bio_url`; sync sets no endpoint)

- [ ] **Step 3: Add `bio_url` to `ConnectorResult`**

In `backend/app/connectors/base.py`:

```python
@dataclass
class ConnectorResult:
    tier: str                                   # api | scrape | manual
    snapshots: list[dict] = field(default_factory=list)
    content: list[dict] = field(default_factory=list)
    bio_url: str | None = None                  # profile bio link, for endpoint auto-match
```

- [ ] **Step 4: Extract bio url in the X connector**

In `backend/app/connectors/x.py`, request the extra fields and extract:

```python
    def fetch(self, account) -> ConnectorResult:
        handle = (account.handle or "").lstrip("@")
        if not handle:
            raise ValueError("account.handle is empty")
        url = (f"https://api.twitter.com/2/users/by/username/{handle}"
               "?user.fields=public_metrics,url,entities")
        data = self._http_get(url, {"Authorization": f"Bearer {self.bearer_token}"})
        user = (data or {}).get("data") or {}
        metrics = user.get("public_metrics") or {}
        followers = metrics.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        bio_url = _bio_url(user)
        return ConnectorResult(tier=self.tier, snapshots=snapshots, bio_url=bio_url)
```

Add a module-level helper:

```python
def _bio_url(user: dict) -> str | None:
    """Prefer the expanded profile URL; fall back to the raw url field."""
    entities = user.get("entities") or {}
    urls = (entities.get("url") or {}).get("urls") or []
    for u in urls:
        expanded = u.get("expanded_url") or u.get("url")
        if expanded:
            return expanded
    return user.get("url") or None
```

- [ ] **Step 5: Auto-match in `sync_account`**

In `backend/app/connectors/sync.py`, after the snapshot/content loop commits, add endpoint auto-match. Import `select`, `Endpoint`, and `match_endpoint`:

```python
from sqlalchemy import inspect as sa_inspect, select
from app.models import ContentItem, Endpoint, Snapshot
from app.flow.match import match_endpoint
```

Then in `sync_account`, before `return`:

```python
    matched_name = None
    if result.bio_url and account.endpoint_id is None:
        endpoints = session.scalars(select(Endpoint)).all()
        ep = match_endpoint(result.bio_url, endpoints)
        if ep is not None:
            account.endpoint_id = ep.id
            matched_name = ep.name
            session.commit()
    return {"snapshots_created": snaps, "content_created": content,
            "tier": result.tier, "endpoint_matched": matched_name}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_connector_sync.py tests/test_connector_x.py -q`
Expected: PASS

- [ ] **Step 7: Full backend suite (regression)**

Run: `./.venv/bin/python -m pytest -q`
Expected: all pass (was 129; now higher with the new tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/connectors/base.py backend/app/connectors/x.py backend/app/connectors/sync.py backend/tests/
git commit -m "feat(connectors): bio-link -> endpoint auto-match on sync (X API real, opt-in for others)"
```

---

## Frontend

### Task 4: Wire FlowConfig to real segment/endpoint pools + real reset

**Files:**
- Modify: `frontend/src/api/types.ts` (ensure `SegmentOut`/`EndpointOut` exported — likely already; verify)
- Modify: `frontend/src/api/client.ts` (add `listSegments`, `listEndpoints`, `resetDemo`)
- Modify: `frontend/src/pages/Flow.tsx` (fetch pools on mount; reset via API)
- Test: `frontend/src/pages/Flow.test.tsx` (extend)

- [ ] **Step 1: Add API client methods**

In `frontend/src/api/client.ts`, inside the `// ---- Flow / 导流 ----` block:

```ts
  listSegments: () => req<SegmentOut[]>("/segments"),
  listEndpoints: () => req<EndpointOut[]>("/endpoints"),
  resetDemo: () => req<{ endpoints: number; segments: number; routed: number }>(
    "/demo/reset", { method: "POST" }),
```

- [ ] **Step 2: Write the failing test**

Extend `frontend/src/pages/Flow.test.tsx` — the stub fetch must answer `/segments`, `/endpoints`, `/demo/reset`. Add a test that the assignable pool is populated from `GET /segments` and `GET /endpoints` on mount (not only session-created), and that clicking "重置为示例" calls `POST /demo/reset`:

```ts
it("populates the assignable pool from GET /segments and /endpoints on mount", async () => {
  // stub: /segments -> [{id:1,label:'crypto'}], /endpoints -> [{id:9,name:'Nina',url_pattern:'linktr.ee/nina'}]
  // render <Flow/>, select an account, assert the 'crypto' segment chip and 'Nina' endpoint option appear
});

it("重置为示例 calls POST /demo/reset", async () => {
  // render, click the reset button, assert a fetch to /demo/reset with method POST occurred
});
```

Write these out fully following the existing Flow.test.tsx stub-fetch pattern (match on `String(url)` suffix; return `{ ok: true, json: async () => ... }`). Include a `/demo/reset` branch and `/segments` + `/endpoints` branches in the stub.

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/pages/Flow.test.tsx` (from `frontend/`)
Expected: FAIL (pool empty until account interaction; no /demo/reset call)

- [ ] **Step 4: Fetch pools on mount in Flow.tsx**

In `Flow.tsx`, lift the segment/endpoint pool to real data:
- Add `const segmentsPool = useAsync(() => api.listSegments(), []);` and `const endpointsPool = useAsync(() => api.listEndpoints(), []);` in the `Flow` component.
- Pass them into `FlowConfig` as props `segmentsPool` / `endpointsPool`.
- In `FlowConfig`, initialize the `segments`/`endpoints` state as a **merge** of the fetched pool plus anything created this session (session-created ids win). Simplest: replace the local `segments`/`endpoints` state with `const [extraSegs, setExtraSegs] = useState<SegmentOut[]>([])` and derive `const segments = mergeById(segmentsPool, extraSegs)`; same for endpoints. On create, push into the `extra*` list AND call `onChanged`-style reload of the pool.
- Keep the existing pattern where segment chips / endpoint select render from `segments`/`endpoints`.

Add a small merge helper (dedupe by id, later wins):

```ts
function mergeById<T extends { id: number }>(base: T[], extra: T[]): T[] {
  const m = new Map<number, T>();
  for (const x of base) m.set(x.id, x);
  for (const x of extra) m.set(x.id, x);
  return [...m.values()];
}
```

- [ ] **Step 5: Replace client-side `seedDemo` with the API reset**

Replace the `seedDemo(accounts)` best-effort function and its two call sites (`EmptyState.reset` and `FlowConfig.resetDemo`) with a call to `api.resetDemo()` followed by the existing `onChanged()`/`reload()`. Delete the now-unused `DEMO_SEGMENTS`, `DEMO_ENDPOINTS`, `DEMO_ASSIGN` constants and the `seedDemo` function and its explanatory comment. After reset, also reload the pools (`segmentsPool.reload()`, `endpointsPool.reload()`).

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run src/pages/Flow.test.tsx`
Expected: PASS

- [ ] **Step 7: Typecheck + full frontend suite**

Run: `npx tsc --noEmit && npx vitest run`
Expected: no type errors; all tests pass

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Flow.tsx frontend/src/pages/Flow.test.tsx
git commit -m "feat(flow-ui): assignable pool from GET /segments+/endpoints, reset via POST /demo/reset"
```

---

### Task 5: Edge-case test coverage (OpsBar + Compare)

**Files:**
- Modify: `frontend/src/components/OpsBar.test.tsx`
- Modify: `frontend/src/pages/Compare.test.tsx`

- [ ] **Step 1: OpsBar — surface a failed batch run**

Add a test: when `POST /batch/run` responds `{ ok: false }`, clicking 跑一批 surfaces an error message to the user (not a silent swallow). Inspect `OpsBar.tsx` first to match the exact error-display element/text; assert on it. If OpsBar currently swallows the error, that is a real bug — fix `OpsBar.tsx` to display it, then the test passes (note the fix in the commit message).

```ts
it("跑一批 surfaces an error when POST /batch/run fails", async () => {
  stubFetch((url, init) => {
    if (init?.method === "POST" && String(url).includes("/batch/run")) {
      return { ok: false, status: 500, json: async () => ({ detail: "boom" }) };
    }
    return undefined;
  });
  render(<OpsBar accounts={ACCOUNTS} />);
  fireEvent.click(screen.getByRole("button", { name: /跑一批/ }));
  expect(await screen.findByText(/boom|失败/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Compare — degenerate id inputs**

Add tests for the edge cases the review flagged:
- `?ids=` (empty) or missing → renders an empty/prompt state without crashing.
- `?ids=1` (single id) → renders one column without crashing.

```ts
it("renders a prompt state when no ids are given", async () => {
  render(<MemoryRouter initialEntries={["/compare"]}><Compare /></MemoryRouter>);
  // assert on whatever Compare renders for the no-selection case (inspect Compare.tsx first)
  expect(await screen.findByText(/选择|对比|compare/i)).toBeInTheDocument();
});

it("renders a single column for ?ids=1 without crashing", async () => {
  render(<MemoryRouter initialEntries={["/compare?ids=1"]}><Compare /></MemoryRouter>);
  expect(await screen.findAllByText("@a1")).toBeTruthy();
});
```

Inspect `Compare.tsx` before finalizing the assertions so they match the real rendered text. If Compare crashes on empty/single ids, that is a real bug — fix `Compare.tsx` to guard it, then the test passes.

- [ ] **Step 3: Run tests to verify they pass**

Run: `npx vitest run src/components/OpsBar.test.tsx src/pages/Compare.test.tsx`
Expected: PASS

- [ ] **Step 4: Full frontend suite (regression)**

Run: `npx vitest run`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/OpsBar.test.tsx frontend/src/pages/Compare.test.tsx frontend/src/components/OpsBar.tsx frontend/src/pages/Compare.tsx
git commit -m "test(ui): OpsBar batch-error + Compare degenerate-ids edge cases"
```

---

## Final review

After all tasks: dispatch a final code review over the whole branch diff, then use `superpowers:finishing-a-development-branch` to merge to `main` (option 1, `--no-ff`). Recreate the local DB before restarting servers so the new `/demo/reset` and pool routes serve fresh data (`rm -f data/matrixloop.db && ./.venv/bin/python seed_demo.py`).
