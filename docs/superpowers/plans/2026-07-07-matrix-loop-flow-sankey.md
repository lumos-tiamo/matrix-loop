# MatrixLoop 导流/转化 桑基流向 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** 借鉴同事「Cube Private Traffic Matrix」，加一层「导流/转化」视图：桑基图 `平台账号 → 用户人群(自定义标签) → 变现出口(具体平台)`。出口用户自定义清单，人群用自定义标签(LLM 归类 + 手动改)，流量边 v1 用粉丝数建模，出口可从账号 bio 外链自动识别。

**诚实边界（已与用户确认）：** 出口 = 自定义具体平台(Nina/xaue…)，可爬 bio 外链自动识别；人群 = 自定义标签(海外投资者/crypto…)，LLM 归类为主 + 手动；流量宽度 = 粉丝数建模(非真实转化)，真转化数留待手动录入/对接出口平台。

**Architecture:** 数据模型加 `Endpoint`(出口)、`AudienceSegment`(人群标签)、`AccountSegment`(账号↔人群 组成，weight)、`Account.endpoint_id`(账号导流去向, nullable→"未定向")。`app/flow/build.py:build_flow(session)` 产出 ECharts Sankey 的 nodes/links（账号→人群→出口，边权=粉丝×人群占比）。写入端点管理出口/人群/组成。LLM `classify_audience` 用 pluggable client(fake 测试) 给账号归人群；连接器可抓 bio 外链 → `match_endpoint` 匹配出口。前端加 ECharts Sankey 视图 + 配置面板 + 重置示例。

**Tech Stack:** 后端 Python/FastAPI(同 venv)；前端 Vite+React+ECharts(同 frontend/)。

**依赖：** 地基 models、plan 3 LLM(`LLMClient`/analyze 模式)、plan 5 API、plan 7 连接器、dashboard-v2 前端设计系统。

---

### Task 1: 数据模型（出口 / 人群 / 组成 / 账号导流去向）

**Files:** Modify `backend/app/models.py`; Test `backend/tests/test_models_flow.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_models_flow.py`:
```python
from app.models import Account, Endpoint, AudienceSegment, AccountSegment


def test_endpoint_and_segment_unique(session):
    session.add_all([Endpoint(name="Nina", url_pattern="linktr.ee/antalpha"),
                     AudienceSegment(label="海外投资者")])
    session.commit()
    assert session.query(Endpoint).one().name == "Nina"
    assert session.query(AudienceSegment).one().label == "海外投资者"


def test_account_composition_and_endpoint(session):
    ep = Endpoint(name="xaue", url_pattern="xaue.com")
    seg = AudienceSegment(label="crypto")
    session.add_all([ep, seg]); session.commit()
    acc = Account(platform="twitter", handle="@a", endpoint_id=ep.id)
    session.add(acc); session.commit()
    session.add(AccountSegment(account_id=acc.id, segment_id=seg.id, weight=0.7))
    session.commit()
    comp = session.query(AccountSegment).filter_by(account_id=acc.id).one()
    assert comp.weight == 0.7
    assert acc.endpoint_id == ep.id
```

- [ ] **Step 2: 运行确认失败** — `python -m pytest tests/test_models_flow.py -v` → ImportError.

- [ ] **Step 3: 追加模型**

Append to `backend/app/models.py`:
```python
class Endpoint(Base):
    __tablename__ = "endpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)          # 自定义出口，如 Nina / xaue
    url_pattern: Mapped[str | None] = mapped_column(String, nullable=True)  # bio 外链匹配子串
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AudienceSegment(Base):
    __tablename__ = "audience_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), unique=True)         # 自定义人群标签，如 海外投资者 / crypto


class AccountSegment(Base):
    __tablename__ = "account_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("audience_segments.id"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)           # 该账号粉丝分到此人群的占比
```

Add to `Account` (after existing columns, before relationships):
```python
    endpoint_id: Mapped[int | None] = mapped_column(ForeignKey("endpoints.id"), nullable=True)
```

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_models_flow.py -v` → PASS (2 passed). Also verify `python -m app.init_db` prints the 3 new tables among the list.

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/models.py backend/tests/test_models_flow.py
git commit -m "feat(flow): Endpoint, AudienceSegment, AccountSegment models + Account.endpoint_id"
```

---

### Task 2: `build_flow` + `GET /flow`

**Files:** Create `backend/app/flow/__init__.py`, `backend/app/flow/build.py`; Modify `backend/app/api/routes.py`; Test `backend/tests/test_flow_build.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_flow_build.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, Endpoint, AudienceSegment, AccountSegment
from app.flow.build import build_flow


def _acct(session, handle, followers, endpoint_id=None):
    acc = Account(platform="twitter", handle=handle, endpoint_id=endpoint_id)
    session.add(acc); session.commit()
    session.add(Snapshot(account_id=acc.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=followers))
    session.commit()
    return acc


def test_flow_edges_follower_weighted(session):
    nina = Endpoint(name="Nina", url_pattern="linktr.ee/x"); session.add(nina); session.commit()
    crypto = AudienceSegment(label="crypto"); overseas = AudienceSegment(label="海外投资者")
    session.add_all([crypto, overseas]); session.commit()

    a = _acct(session, "@a", 10000, endpoint_id=nina.id)
    session.add_all([
        AccountSegment(account_id=a.id, segment_id=crypto.id, weight=0.6),
        AccountSegment(account_id=a.id, segment_id=overseas.id, weight=0.4),
    ])
    session.commit()

    flow = build_flow(session)
    names = {n["name"] for n in flow["nodes"]}
    assert "acct:@a" in names and "seg:crypto" in names and "ep:Nina" in names
    links = {(l["source"], l["target"]): l["value"] for l in flow["links"]}
    # account -> segment weighted by follower share
    assert links[("acct:@a", "seg:crypto")] == 6000
    assert links[("acct:@a", "seg:海外投资者")] == 4000
    # segment -> endpoint (account routes whole flow to its endpoint)
    assert links[("seg:crypto", "ep:Nina")] == 6000
    assert links[("seg:海外投资者", "ep:Nina")] == 4000


def test_flow_unrouted_account_goes_to_placeholder(session):
    seg = AudienceSegment(label="crypto"); session.add(seg); session.commit()
    a = _acct(session, "@b", 5000, endpoint_id=None)   # no endpoint
    session.add(AccountSegment(account_id=a.id, segment_id=seg.id, weight=1.0)); session.commit()
    flow = build_flow(session)
    links = {(l["source"], l["target"]): l["value"] for l in flow["links"]}
    assert links[("seg:crypto", "ep:未定向")] == 5000


def test_flow_empty_is_valid(session):
    flow = build_flow(session)
    assert flow == {"nodes": [], "links": []}
```

- [ ] **Step 2: 运行确认失败** — ModuleNotFoundError app.flow.

- [ ] **Step 3: 实现**

Create `backend/app/flow/__init__.py` (空).

Create `backend/app/flow/build.py`:
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountSegment, AudienceSegment, Endpoint, Snapshot

UNROUTED = "未定向"


def _latest_followers(session: Session, account_id: int) -> int:
    snap = session.scalars(
        select(Snapshot).where(Snapshot.account_id == account_id)
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
    ).first()
    return (snap.followers or 0) if snap else 0


def build_flow(session: Session) -> dict:
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())
    segments = {s.id: s.label for s in session.scalars(select(AudienceSegment)).all()}
    endpoints = {e.id: e.name for e in session.scalars(select(Endpoint)).all()}

    links: dict[tuple[str, str], float] = {}
    used: set[str] = set()

    def add(src: str, tgt: str, val: float) -> None:
        if val <= 0:
            return
        links[(src, tgt)] = links.get((src, tgt), 0.0) + val
        used.add(src); used.add(tgt)

    for a in accounts:
        comps = list(session.scalars(select(AccountSegment).where(AccountSegment.account_id == a.id)).all())
        if not comps:
            continue
        followers = _latest_followers(session, a.id)
        if followers <= 0:
            continue
        wsum = sum(c.weight for c in comps) or 1.0
        ep_name = endpoints.get(a.endpoint_id, UNROUTED) if a.endpoint_id else UNROUTED
        acct_node = f"acct:{a.handle}"
        for c in comps:
            label = segments.get(c.segment_id)
            if label is None:
                continue
            flow = followers * c.weight / wsum
            seg_node = f"seg:{label}"
            add(acct_node, seg_node, flow)
            add(seg_node, f"ep:{ep_name}", flow)

    nodes = [{"name": n} for n in sorted(used)]
    link_list = [{"source": s, "target": t, "value": round(v)} for (s, t), v in links.items()]
    return {"nodes": nodes, "links": link_list}
```

Add to `backend/app/api/routes.py`:
```python
from app.flow.build import build_flow
...
@router.get("/flow")
def flow(db: Session = Depends(get_db)) -> dict:
    return build_flow(db)
```

- [ ] **Step 4: 运行确认通过** — PASS (3 passed).

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/flow backend/app/api/routes.py backend/tests/test_flow_build.py
git commit -m "feat(flow): build_flow sankey (account->segment->endpoint, follower-weighted, 未定向 fallback) + GET /flow"
```

---

### Task 3: 写入端点 + `match_endpoint`

**Files:** Modify `backend/app/api/routes.py`, `backend/app/api/schemas.py`, Create `backend/app/flow/match.py`; Test `backend/tests/test_flow_writes.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_flow_writes.py`:
```python
from app.models import Account, Endpoint, AudienceSegment, AccountSegment
from app.flow.match import match_endpoint


def test_match_endpoint_by_url_substring(session):
    eps = [Endpoint(name="Nina", url_pattern="linktr.ee/antalpha"), Endpoint(name="xaue", url_pattern="xaue.com")]
    assert match_endpoint("https://xaue.com/protocol", eps).name == "xaue"
    assert match_endpoint("https://example.com", eps) is None


def test_create_segment_and_endpoint(client, session):
    assert client.post("/segments", json={"label": "crypto"}).status_code == 201
    assert client.post("/endpoints", json={"name": "Nina", "url_pattern": "linktr.ee/x"}).status_code == 201
    assert session.query(AudienceSegment).count() == 1
    assert session.query(Endpoint).count() == 1


def test_set_account_composition_and_endpoint(client, session):
    ep = Endpoint(name="Nina"); seg = AudienceSegment(label="crypto")
    session.add_all([ep, seg]); session.commit()
    acc = Account(platform="twitter", handle="@a"); session.add(acc); session.commit()

    r1 = client.post(f"/accounts/{acc.id}/segments", json={"segments": [{"segment_id": seg.id, "weight": 0.8}]})
    assert r1.status_code == 200
    assert session.query(AccountSegment).filter_by(account_id=acc.id).one().weight == 0.8

    r2 = client.post(f"/accounts/{acc.id}/endpoint", json={"endpoint_id": ep.id})
    assert r2.status_code == 200
    session.refresh(acc)
    assert acc.endpoint_id == ep.id
```

- [ ] **Step 2: 运行确认失败.**

- [ ] **Step 3: 实现**

Create `backend/app/flow/match.py`:
```python
from __future__ import annotations


def match_endpoint(url: str, endpoints):
    """Return the first endpoint whose url_pattern is a substring of url, else None."""
    u = (url or "").lower()
    for ep in endpoints:
        pat = (ep.url_pattern or "").lower()
        if pat and pat in u:
            return ep
    return None
```

Add schemas to `backend/app/api/schemas.py`:
```python
class SegmentCreate(BaseModel):
    label: str

class EndpointCreate(BaseModel):
    name: str
    url_pattern: str | None = None

class CompositionItem(BaseModel):
    segment_id: int
    weight: float = 1.0

class SetComposition(BaseModel):
    segments: list[CompositionItem]

class SetEndpoint(BaseModel):
    endpoint_id: int | None = None
```

Append routes to `backend/app/api/routes.py` (import `AudienceSegment, Endpoint, AccountSegment` in the models import line):
```python
@router.post("/segments", status_code=201)
def create_segment(payload: schemas.SegmentCreate, db: Session = Depends(get_db)) -> dict:
    seg = AudienceSegment(label=payload.label)
    db.add(seg); db.commit()
    return {"id": seg.id, "label": seg.label}


@router.post("/endpoints", status_code=201)
def create_endpoint(payload: schemas.EndpointCreate, db: Session = Depends(get_db)) -> dict:
    ep = Endpoint(name=payload.name, url_pattern=payload.url_pattern)
    db.add(ep); db.commit()
    return {"id": ep.id, "name": ep.name, "url_pattern": ep.url_pattern}


@router.post("/accounts/{account_id}/segments")
def set_composition(account_id: int, payload: schemas.SetComposition, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    db.query(AccountSegment).filter_by(account_id=account_id).delete()
    for item in payload.segments:
        db.add(AccountSegment(account_id=account_id, segment_id=item.segment_id, weight=item.weight))
    db.commit()
    return {"account_id": account_id, "count": len(payload.segments)}


@router.post("/accounts/{account_id}/endpoint")
def set_endpoint(account_id: int, payload: schemas.SetEndpoint, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    acc.endpoint_id = payload.endpoint_id
    db.commit()
    return {"account_id": account_id, "endpoint_id": acc.endpoint_id}
```

- [ ] **Step 4: 运行确认通过** — PASS (3 passed).

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/flow/match.py backend/app/api/routes.py backend/app/api/schemas.py backend/tests/test_flow_writes.py
git commit -m "feat(flow): match_endpoint + write endpoints (create segment/endpoint, set account composition/endpoint)"
```

---

### Task 4: LLM 人群归类 + bio 外链自动识别出口

**Files:** Create `backend/app/flow/classify.py`; Modify `backend/app/api/routes.py`; Test `backend/tests/test_flow_classify.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_flow_classify.py`:
```python
import json

from app.models import Account, ContentItem, AudienceSegment
from app.flow.classify import classify_audience


class FakeLLMClient:
    def __init__(self, response): self.response = response; self.calls = []
    def complete(self, *, system, prompt): self.calls.append(prompt); return self.response


def test_classify_audience_returns_matching_labels():
    acc = Account(platform="twitter", handle="@a", positioning="crypto macro")
    content = [ContentItem(account_id=1, topic="bitcoin"), ContentItem(account_id=1, topic="defi")]
    client = FakeLLMClient(json.dumps({"segments": ["crypto", "海外投资者"]}))
    labels = classify_audience(acc, content, client, ["crypto", "海外投资者", "宝妈"])
    assert labels == ["crypto", "海外投资者"]
    assert "crypto" in client.calls[0]  # candidate labels in prompt


def test_classify_audience_filters_unknown_labels():
    acc = Account(platform="x", handle="@a")
    client_ = type("C", (), {"complete": lambda self, *, system, prompt: json.dumps({"segments": ["crypto", "bogus"]})})()
    labels = classify_audience(acc, [], client_, ["crypto", "海外投资者"])
    assert labels == ["crypto"]      # 'bogus' not in candidate set -> dropped
```

- [ ] **Step 2: 运行确认失败.**

- [ ] **Step 3: 实现**

Create `backend/app/flow/classify.py`:
```python
from __future__ import annotations

import json

_SYSTEM = "You classify a social account's audience into given segment tags. Respond ONLY with JSON."


def classify_audience(account, content_items, client, candidate_labels: list[str]) -> list[str]:
    topics = [c.topic for c in content_items if getattr(c, "topic", None)]
    prompt = "\n".join([
        f"Account: {account.handle} ({account.platform})",
        f"Positioning: {account.positioning or '(none)'}",
        f"Recent topics: {topics if topics else '(none)'}",
        f"Candidate audience segments: {candidate_labels}",
        'Return JSON {"segments": ["<label from candidates>", ...]} - only labels from the candidate list that fit.',
    ])
    raw = client.complete(system=_SYSTEM, prompt=prompt)
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start:end + 1]) if start != -1 and end != -1 else {}
    picked = data.get("segments", []) if isinstance(data, dict) else []
    allowed = set(candidate_labels)
    return [s for s in picked if s in allowed]
```

Append route to `backend/app/api/routes.py` (build a real Claude client from config, fall back gracefully; endpoint assigns matched segments, creating any missing ones):
```python
from app.flow.classify import classify_audience
from app.analysis.claude_client import ClaudeClient
...
@router.post("/accounts/{account_id}/classify-audience")
def classify_audience_endpoint(account_id: int, db: Session = Depends(get_db)) -> dict:
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="account not found")
    labels = [s.label for s in db.scalars(select(AudienceSegment)).all()]
    if not labels:
        raise HTTPException(status_code=422, detail="先创建人群标签(/segments)再归类")
    try:
        client = ClaudeClient()
    except Exception as exc:  # noqa: BLE001 - no key configured
        raise HTTPException(status_code=422, detail=f"LLM 未配置：{exc}") from exc
    content = list(db.scalars(select(ContentItem).where(ContentItem.account_id == account_id)).all())
    picked = classify_audience(acc, content, client, labels)
    seg_by_label = {s.label: s for s in db.scalars(select(AudienceSegment)).all()}
    db.query(AccountSegment).filter_by(account_id=account_id).delete()
    for lbl in picked:
        db.add(AccountSegment(account_id=account_id, segment_id=seg_by_label[lbl].id, weight=1.0))
    db.commit()
    return {"account_id": account_id, "segments": picked}
```

Note: bio-link → endpoint auto-match reuses `match_endpoint` (Task 3). A future connector enhancement can fetch bio links and call `match_endpoint`; for v1 the endpoint is set via `/accounts/{id}/endpoint` (Task 3) or matched when a bio URL is supplied. Keep this task to the LLM classify endpoint + tests (the endpoint-from-bio wiring lands when connectors expose bio; do not add a live scraper here).

- [ ] **Step 4: 运行确认通过** — PASS (2 passed).

- [ ] **Step 5: 全后端回归** — `python -m pytest -q`（应 104 + T1(2)+T2(3)+T3(3)+T4(2) = 114 passed）。

- [ ] **Step 6: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/flow/classify.py backend/app/api/routes.py backend/tests/test_flow_classify.py
git commit -m "feat(flow): LLM classify_audience + POST /accounts/{id}/classify-audience (assigns segments)"
```

---

### Task 5: 前端 - 桑基视图 + 配置面板 + 重置示例

**Files:** Create `frontend/src/pages/Flow.tsx`, `frontend/src/components/SankeyChart.tsx`, `frontend/src/pages/FlowConfig.tsx` (or a panel); Modify `App.tsx`(路由 `/flow`), `Layout.tsx`(导航), `api/types.ts`+`api/client.ts`(getFlow, createSegment, createEndpoint, setComposition, setEndpoint, classifyAudience); extend `backend/seed_demo.py` to seed endpoints/segments/compositions; Test `Flow.test.tsx`.

- [ ] **Step 1** `api/client.ts` 加 `getFlow()`(GET /flow)、`createSegment(label)`、`createEndpoint(name,url_pattern?)`、`setComposition(accountId, segments)`、`setEndpoint(accountId, endpointId)`、`classifyAudience(accountId)`；`api/types.ts` 加 `FlowData {nodes:{name}[]; links:{source,target,value}[]}`。

- [ ] **Step 2（TDD）** 写 `Flow.test.tsx`：mock `echarts-for-react`，stub `/flow` 返回含 acct/seg/ep 节点与 links 的对象；断言页面渲染出桑基容器（mock echart testid）+ 图例/统计（节点数、总流量）。先 FAIL。

- [ ] **Step 3** 实现：
  - `SankeyChart.tsx`：ECharts `series:[{type:"sankey"}]`，深色主题 + 多色节点（账号青柠 / 人群青 / 出口紫），links 半透明渐变；消费 `{nodes, links}`。节点名去掉 `acct:/seg:/ep:` 前缀显示。
  - `Flow.tsx`（路由 `/flow`）：顶部标题「导流/转化流向」+ 说明（流量宽度=粉丝建模，非真实转化）+ SankeyChart（占大屏）+ 右侧/下方一个小配置面板 `FlowConfig`：新建人群标签、新建出口、给账号选人群占比 + 选出口 + 「LLM 归类人群」按钮（classifyAudience）+ 「重置为示例」。操作后 reload /flow。v2 卡片风格。
  - `App.tsx` 加 `/flow` 路由；`Layout` 导航加「导流」。
  - `backend/seed_demo.py`：追加 seed 若干 Endpoint（Nina/xaue/未定向靠 null）、AudienceSegment（crypto/海外投资者/宝妈…）、给部分 demo 账号加 AccountSegment 组成 + endpoint_id，让 `/flow` 有 demo 桑基。（idempotent：已 seed 就跳过这部分。）

- [ ] **Step 4** `npx vitest run` 全绿 + `npm run build` 干净。

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add frontend backend/seed_demo.py
git commit -m "feat(flow): Sankey 导流流向 view + config panel + demo seed (account->audience->endpoint)"
```

---

## 完成标准

- 后端 `python -m pytest` 全绿（~114：models 2 + build 3 + writes 3 + classify 2 加进 104）
- 前端 build 干净 + vitest 全绿；桑基视图消费 `/flow`，配置面板可建人群/出口/组成、LLM 归类、重置示例
- 桑基图渲染 `账号 → 人群(自定义) → 出口(自定义)`，流量宽度=粉丝建模，无端点账号归「未定向」
- 诚实边界：流量非真实转化（粉丝建模）；bio 自动识别出口靠 `match_endpoint`（连接器抓 bio 的实网接入留待后续）；真转化数手动/对接
- 视觉最终由浏览器截图人工核验（seed_demo 已含导流 demo → uvicorn → npm run dev → 截图桑基）
