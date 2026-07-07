# MatrixLoop Dashboard v2（大屏 BI 重做）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 把 Dashboard 从「2 页干瘪表格」重做成「深色 BI 大屏 + 活泼」的完整操盘台：矩阵大屏总览（KPI 卡 + 平台健康热力图 + 大盘趋势 + 告警中心 + 飙升榜 + 定位分布 + 可筛选账号矩阵卡）、账号对比、爆文库、批量/导入/同步可视化、更丰富的下钻页。后端补两个聚合端点。

**视觉源真相（务必打开对照）：** `frontend/design/overview-mockup.html` - 已获用户签字的高保真样。实现的观感/配色/卡片布局要对齐它。用浏览器打开它对照像素级细节。

**Architecture:** 后端加 `app/api/overview.py`（`build_overview(session)->dict`）+ `GET /overview`，以及 `GET /content`（跨账号内容库）。前端升级设计令牌（多色 BI）、真 ECharts 图、新增页面与功能。真 ECharts 组件在测试里 mock（`vi.mock("echarts-for-react")`）。

**Tech Stack:** 后端 Python/FastAPI（同 venv）；前端 Vite+React+TS+Tailwind+ECharts（同 frontend/）。

**设计令牌 v2（Tailwind theme.extend.colors）：**
```
bg #090C12 · panel #11151F · panel2 #151A26 · line #232B3C · text #EAEDF3 · muted #8A93A8 · dim #5C6579
lime #B6FF3C · cyan #4CD4F0 · violet #A78BFA · pink #FF6FB5 · good #38E08A · warn #FFB020 · alert #FF5C7A
```
卡片 = `linear-gradient(180deg,panel2,panel)` + `border line` + `rounded-2xl`；数字用 IBM Plex Mono tabular-nums；标题 Archivo；正文 Noto Sans SC；噪点/双径向光背景（见 mockup body）。

---

### Task 1: 后端 `GET /overview` 聚合端点

**Files:** Create `backend/app/api/overview.py`; Modify `backend/app/api/routes.py`; Test `backend/tests/test_api_overview.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_api_overview.py`:
```python
from datetime import datetime, timezone

from app.models import Account, Snapshot, ContentItem, LoopRun, Evaluation, Recommendation, Draft


def _seed(session):
    a1 = Account(platform="xiaohongshu", handle="@a1")
    a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100000, engagement_rate=0.05),
        Snapshot(account_id=a1.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=112000, engagement_rate=0.06),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=50000, engagement_rate=0.03),
        Snapshot(account_id=a2.id, ts=datetime(2026, 7, 6, tzinfo=timezone.utc), followers=49000, engagement_rate=0.03),
    ])
    r1 = LoopRun(account_id=a1.id, status="ok")
    r1.evaluation = Evaluation(account_id=a1.id, composite_score=88.0, breakdown={"growth": 90, "engagement": 80, "commercial": 60, "positioning": 92})
    r1.recommendations.append(Recommendation(kind="positioning", content="x", status="pending"))
    r1.drafts.append(Draft(kind="topic", content="t", review_status="pending"))
    r2 = LoopRun(account_id=a2.id, status="no_progress")
    r2.evaluation = Evaluation(account_id=a2.id, composite_score=40.0, breakdown={"growth": 20, "engagement": 50, "commercial": 40, "positioning": 30})
    session.add_all([r1, r2]); session.commit()
    return a1, a2


def test_overview_kpis_and_sections(client, session):
    a1, a2 = _seed(session)
    body = client.get("/overview").json()

    assert body["kpis"]["total_accounts"] == 2
    assert body["kpis"]["platforms"] == 2
    assert body["kpis"]["needs_attention"] == 1          # a2 no_progress
    assert body["kpis"]["pending_review"] == 2           # 1 rec + 1 draft pending
    assert body["kpis"]["avg_score"] == 64.0             # (88+40)/2

    plats = {p["platform"]: p for p in body["platform_health"]}
    assert plats["xiaohongshu"]["growth"] == 90
    assert plats["twitter"]["positioning"] == 30

    # matrix-wide trend aggregated by date
    trend = {t["date"]: t for t in body["trend"]}
    assert trend["2026-07-01"]["followers"] == 150000    # 100k + 50k
    assert trend["2026-07-06"]["followers"] == 161000    # 112k + 49k

    # alerts include the no_progress account
    kinds = {(a["account_id"], a["kind"]) for a in body["alerts"]}
    assert (a2.id, "no_progress") in kinds

    # top movers: a1 +12000, a2 -1000
    movers = {m["account_id"]: m["delta_followers"] for m in body["top_movers"]}
    assert movers[a1.id] == 12000
    assert movers[a2.id] == -1000

    dist = body["positioning_distribution"]
    assert dist["clear"] == 1 and dist["scattered"] == 1   # a1 pos 92 clear, a2 pos 30 scattered
```

- [ ] **Step 2: 运行确认失败** — `python -m pytest tests/test_api_overview.py -v` → FAIL (route missing).

- [ ] **Step 3: 实现 overview.py**

Create `backend/app/api/overview.py`:
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, ContentItem, Draft, Evaluation, LoopRun, Recommendation, Snapshot


def _latest_eval(session, account_id):
    return session.scalars(
        select(Evaluation).where(Evaluation.account_id == account_id)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    ).first()


def _latest_loop(session, account_id):
    return session.scalars(
        select(LoopRun).where(LoopRun.account_id == account_id)
        .order_by(LoopRun.ts.desc(), LoopRun.id.desc())
    ).first()


def _ordered_snaps(session, account_id):
    return session.scalars(
        select(Snapshot).where(Snapshot.account_id == account_id).order_by(Snapshot.ts)
    ).all()


def build_overview(session: Session) -> dict:
    accounts = list(session.scalars(select(Account).order_by(Account.id)).all())

    evals = {a.id: _latest_eval(session, a.id) for a in accounts}
    loops = {a.id: _latest_loop(session, a.id) for a in accounts}

    scored = [evals[a.id].composite_score for a in accounts if evals[a.id]]
    avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0
    needs_attention = sum(1 for a in accounts if loops[a.id] and loops[a.id].status == "no_progress")
    pending_recs = session.scalars(select(Recommendation).where(Recommendation.status == "pending")).all()
    pending_drafts = session.scalars(select(Draft).where(Draft.review_status == "pending")).all()

    # platform health: avg of latest-eval breakdown per objective, grouped by platform
    dims = ["growth", "engagement", "commercial", "positioning"]
    by_platform: dict[str, list] = {}
    for a in accounts:
        ev = evals[a.id]
        if ev:
            by_platform.setdefault(a.platform, []).append(ev.breakdown or {})
    platform_health = []
    for platform, rows in by_platform.items():
        entry = {"platform": platform}
        for d in dims:
            vals = [r.get(d, 0) for r in rows]
            entry[d] = round(sum(vals) / len(vals), 1) if vals else 0.0
        platform_health.append(entry)

    # matrix-wide trend: aggregate followers + avg engagement by snapshot date
    trend_acc: dict[str, dict] = {}
    for a in accounts:
        for s in _ordered_snaps(session, a.id):
            day = s.ts.date().isoformat()
            t = trend_acc.setdefault(day, {"date": day, "followers": 0, "_er": [], })
            t["followers"] += s.followers or 0
            if s.engagement_rate is not None:
                t["_er"].append(s.engagement_rate)
    trend = []
    for day in sorted(trend_acc):
        t = trend_acc[day]
        er = t.pop("_er")
        t["engagement"] = round(sum(er) / len(er), 4) if er else 0.0
        trend.append(t)

    # alerts
    alerts = []
    for a in accounts:
        lp = loops[a.id]
        if lp and lp.status == "no_progress":
            alerts.append({"account_id": a.id, "handle": a.handle, "platform": a.platform,
                           "kind": "no_progress", "detail": "连续无进展，需介入"})
    pend_draft_by_acct: dict[int, int] = {}
    for d in pending_drafts:
        acct = d.loop_run.account_id
        pend_draft_by_acct[acct] = pend_draft_by_acct.get(acct, 0) + 1
    handle_by_id = {a.id: a for a in accounts}
    for acct_id, n in pend_draft_by_acct.items():
        a = handle_by_id.get(acct_id)
        if a:
            alerts.append({"account_id": acct_id, "handle": a.handle, "platform": a.platform,
                           "kind": "pending_drafts", "detail": f"{n} 条草稿待审"})

    # top movers: latest followers - previous followers
    movers = []
    for a in accounts:
        snaps = _ordered_snaps(session, a.id)
        if len(snaps) >= 2 and snaps[-1].followers is not None and snaps[-2].followers is not None:
            movers.append({"account_id": a.id, "handle": a.handle, "platform": a.platform,
                           "delta_followers": snaps[-1].followers - snaps[-2].followers})
    movers.sort(key=lambda m: m["delta_followers"], reverse=True)

    # positioning distribution from latest eval positioning subscore
    dist = {"clear": 0, "ok": 0, "scattered": 0}
    for a in accounts:
        ev = evals[a.id]
        if ev:
            p = (ev.breakdown or {}).get("positioning", 0)
            dist["clear" if p >= 70 else "scattered" if p < 40 else "ok"] += 1

    return {
        "kpis": {
            "total_accounts": len(accounts),
            "avg_score": avg_score,
            "needs_attention": needs_attention,
            "platforms": len({a.platform for a in accounts}),
            "pending_review": len(pending_recs) + len(pending_drafts),
        },
        "platform_health": platform_health,
        "trend": trend,
        "alerts": alerts,
        "top_movers": movers[:10],
        "positioning_distribution": dist,
    }
```

Add to `backend/app/api/routes.py` imports:
```python
from app.api.overview import build_overview
```
Append route:
```python
@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return build_overview(db)
```

- [ ] **Step 4: 运行确认通过** — `python -m pytest tests/test_api_overview.py -v` → PASS (1 passed).

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/overview.py backend/app/api/routes.py backend/tests/test_api_overview.py
git commit -m "feat(api): GET /overview aggregate (kpis, platform health, trend, alerts, movers, positioning dist)"
```

---

### Task 2: 后端 `GET /content` 爆文库端点

**Files:** Modify `backend/app/api/routes.py` + `backend/app/api/schemas.py`; Test `backend/tests/test_api_content.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_api_content.py`:
```python
from app.models import Account, ContentItem


def _seed(session):
    a1 = Account(platform="xiaohongshu", handle="@a1")
    a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        ContentItem(account_id=a1.id, topic="beauty", views=5000, likes=400),
        ContentItem(account_id=a1.id, topic="skincare", views=1200, likes=90),
        ContentItem(account_id=a2.id, topic="macro", views=8000, likes=600),
    ])
    session.commit()
    return a1, a2


def test_content_lists_sorted_by_views_with_account(client, session):
    a1, a2 = _seed(session)
    items = client.get("/content").json()
    assert [i["views"] for i in items] == [8000, 5000, 1200]     # views desc
    top = items[0]
    assert top["account_handle"] == "@a2"
    assert top["platform"] == "twitter"


def test_content_filter_by_platform(client, session):
    _seed(session)
    items = client.get("/content?platform=xiaohongshu").json()
    assert len(items) == 2
    assert all(i["platform"] == "xiaohongshu" for i in items)
```

- [ ] **Step 2: 运行确认失败** — FAIL (route missing).

- [ ] **Step 3: 实现**

Add to `backend/app/api/schemas.py`:
```python
class ContentLibraryItem(BaseModel):
    id: int
    account_id: int
    account_handle: str
    platform: str
    topic: str | None
    views: int | None
    likes: int | None
    comments: int | None
    published_at: datetime | None
```

Append to `backend/app/api/routes.py`:
```python
@router.get("/content", response_model=list[schemas.ContentLibraryItem])
def content_library(platform: str | None = None, account_id: int | None = None,
                    limit: int = 200, db: Session = Depends(get_db)) -> list[schemas.ContentLibraryItem]:
    stmt = select(ContentItem, Account).join(Account, ContentItem.account_id == Account.id)
    if platform:
        stmt = stmt.where(Account.platform == platform)
    if account_id:
        stmt = stmt.where(ContentItem.account_id == account_id)
    rows = db.execute(stmt).all()
    items = [
        schemas.ContentLibraryItem(
            id=ci.id, account_id=ci.account_id, account_handle=acc.handle, platform=acc.platform,
            topic=ci.topic, views=ci.views, likes=ci.likes, comments=ci.comments, published_at=ci.published_at,
        )
        for ci, acc in rows
    ]
    items.sort(key=lambda i: (i.views or 0), reverse=True)
    return items[:limit]
```
(Ensure `ContentItem` is imported in routes.py — add to the models import.)

- [ ] **Step 4: 运行确认通过** — PASS (2 passed).

- [ ] **Step 5: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add backend/app/api/routes.py backend/app/api/schemas.py backend/tests/test_api_content.py
git commit -m "feat(api): GET /content cross-account library (join account, filter platform/account, sort views)"
```

- [ ] **Step 6: 全后端回归** — `python -m pytest -q`（应 ~103 passed：100 + overview 1 + content 2）。

---

### Task 3: 前端设计系统 v2 + Overview 大屏（核心，对齐 mockup）

**Files:** Modify `frontend/tailwind.config.ts`, `frontend/src/index.css`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`; Create chart + card components; Rewrite `frontend/src/pages/Overview.tsx`; Test `frontend/src/pages/Overview.test.tsx`

**先打开 `frontend/design/overview-mockup.html` 对照。** 观感必须接近它。

- [ ] **Step 1** 更新 `tailwind.config.ts` 的 `theme.extend.colors` 为设计令牌 v2（见本 plan 顶部色值），字体不变。更新 `index.css` 的 body 背景为 mockup 里的双径向光 + 噪点、`.rise` 错峰淡入保留、新增 `.tabnums`。

- [ ] **Step 2** `api/types.ts` 追加 `Overview` 类型（kpis / platform_health[] / trend[] / alerts[] / top_movers[] / positioning_distribution），`api/client.ts` 追加 `getOverview()`（GET /overview）与 `getContent(params)`（GET /content）。

- [ ] **Step 3（TDD）** 写 `Overview.test.tsx`：mock `echarts-for-react`，stub `fetch` 使 `/overview` 返回一个含 2 平台、needs_attention=1、一条 no_progress alert 的对象，`/accounts` 返回账号列表；断言渲染出 KPI 数字（如 total_accounts、avg_score）、平台健康行、告警条（含 no_progress handle）、账号卡（handle）。先跑确认 FAIL。

- [ ] **Step 4** 实现组件并重写 Overview：
  - `components/KpiCard.tsx`（label + 大号数字 + delta + 迷你 sparkline via ECharts line, 无坐标轴）
  - `components/HeatmapCard.tsx`（平台 × 4 目标网格，单元格按分值上色 red→amber→lime；用 CSS grid + 背景色，不必用 echarts）
  - `components/TrendCard.tsx`（ECharts 面积图：followers 青柠 + engagement 青，双 y 轴或归一）
  - `components/AlertCenter.tsx`（alerts 列表，按 kind 上色点 + 操作按钮链到下钻）
  - `components/MoversCard.tsx`（top_movers 条形）
  - `components/PositioningDonut.tsx`（ECharts 环形：clear/ok/scattered）
  - `components/AccountCard.tsx`（价值分环 conic-gradient + 状态标签 + 指标 + sparkline）
  - `components/FilterBar.tsx`（搜索框 + 平台 chips + 排序切换）
  - `Overview.tsx`：顶部 FilterBar → KPI 行（5 卡）→ 热力图 + 趋势（two）→ 告警 + 飙升 + 定位环（three）→ 账号矩阵卡（按平台分组、支持搜索/平台筛选/排序）。数据来自 `getOverview()` + `getAccounts()`。布局/间距/圆角/配色对齐 mockup。
  - 顶部「⚡ 跑一批」按钮调用 `api.batchRun()`（POST /batch/run，client 追加该方法）后 reload。

- [ ] **Step 5** `npx vitest run src/pages/Overview.test.tsx` PASS，且 `npm run build` 干净。

- [ ] **Step 6: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add frontend
git commit -m "feat(dashboard-v2): BI design tokens + Overview 大屏 (KPIs, heatmap, trend, alerts, movers, donut, account cards, filters)"
```

---

### Task 4: 前端 - 账号对比 + 爆文库 + 批量/导入/同步

**Files:** Create `frontend/src/pages/Compare.tsx`, `frontend/src/pages/ContentLibrary.tsx`, `frontend/src/components/OpsBar.tsx`; Modify `App.tsx`（加路由 `/compare`, `/content`）、`api/client.ts`（`importSnapshots(csv)`, `syncAccount(id)`, `batchRun(sync)` 已在 T3 加）; Test 各页 smoke。

- [ ] **Step 1（TDD）** 分别为 Compare、ContentLibrary 写 smoke 测试（mock fetch）：
  - Compare：选 2 个账号（用 query `?ids=1,2` 或多选），并排展示各自价值分 + KPI + 迷你趋势；断言两账号 handle 都出现。
  - ContentLibrary：`/content` 返回若干内容，渲染成表/卡，按 views 降序，平台筛选 chip；断言最高 views 的内容在最前。
  先跑确认 FAIL。

- [ ] **Step 2** 实现：
  - `ContentLibrary.tsx`：消费 `getContent({platform})`，卡片/表格展示 topic/views/likes/账号/平台，平台 chip 筛选，按 views 排序（爆文置顶）。风格同 v2。
  - `Compare.tsx`：从 `/accounts` 选 2-3 个（简单多选下拉或复选），对每个 `getAccount(id)`，并排渲染价值分环 + KPI + 评估雷达（复用 T5 的 ScoreRadar 或 T3 组件）。
  - `OpsBar.tsx`（放 Layout 顶部或 Overview）：`⚡ 跑一批`（batchRun）、`📥 导入 CSV`（弹一个 textarea → importSnapshots）、`🔌 同步账号`（对当前筛选/选中账号 syncAccount，manual 平台提示走导入）。操作后 toast/reload，失败显示错误。
  - `App.tsx` 加 `/compare`、`/content` 路由，Layout 导航加入口。

- [ ] **Step 3** vitest 两页 PASS + `npm run build` 干净。

- [ ] **Step 4: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add frontend
git commit -m "feat(dashboard-v2): account compare, content library, ops bar (batch/import/sync)"
```

---

### Task 5: 前端 - 下钻页 v2

**Files:** Rewrite `frontend/src/pages/AccountDetail.tsx`; Create `frontend/src/components/EffectCurve.tsx`, `frontend/src/components/GoalProgress.tsx`; Test 更新 `AccountDetail.test.tsx`

- [ ] **Step 1（TDD）** 更新 `AccountDetail.test.tsx`（mock echarts）：DETAIL mock 含 2 个 loop_runs（不同 composite），断言渲染：大号价值分、多指标 KPI、Loop 见效对比曲线（EffectCurve，用两轮 composite）、目标进度（GoalProgress，用 objective_weights + 最新 breakdown）、待审面板（采纳/否决沿用）。先 FAIL。

- [ ] **Step 2** 实现：
  - `EffectCurve.tsx`：ECharts 折线，x=历轮（loop_runs 按时间），y=composite_score，标注每轮 verify delta（见效↑/无效→）。
  - `GoalProgress.tsx`：按 `objective_weights` 四目标 + 最新 `evaluation.breakdown`，画四条进度条（子分 / 100）+ 显示权重；顶部显示 `acceptance_criteria`（若有）。
  - `AccountDetail.tsx` 重写为 v2 风格：头部（platform/handle + 大号青柠价值分 + 跑一轮/同步按钮）→ KPI 行 → 多指标趋势（TrendCard 复用，多线：粉丝/互动）+ 评估雷达 → EffectCurve + GoalProgress → Loop 历史时间线 + 待审产出面板（采纳/否决 + 起草）。配色/卡片对齐 v2。

- [ ] **Step 3** 全前端 `npx vitest run` PASS + `npm run build` 干净。

- [ ] **Step 4: 提交**
```bash
cd /Users/aa00102/matrix-loop
git add frontend
git commit -m "feat(dashboard-v2): account detail v2 - multi-metric trends, loop effect curve, goal progress"
```

---

## 完成标准

- 后端：`python -m pytest` 全绿（含 /overview、/content 新测试，~103+）
- 前端：`npm run build` 干净、`npx vitest run` 全绿（各页 smoke）
- 观感对齐 `frontend/design/overview-mockup.html`（深色 BI + 多色 + 卡片 + 图表 + 活泼）
- 功能齐：大屏总览（KPI/热力图/趋势/告警/飙升/定位环/账号卡 + 搜索筛选分组）、账号对比、爆文库、批量/导入/同步界面、下钻 v2（多指标趋势 + Loop 见效曲线 + 目标进度）
- 视觉最终由浏览器截图人工核验（seed_demo → uvicorn → npm run dev → 截图）
- 备注：500 账号的 `/batch/run` 后台异步化仍留待后续；本计划聚焦「好看 + 功能齐」
