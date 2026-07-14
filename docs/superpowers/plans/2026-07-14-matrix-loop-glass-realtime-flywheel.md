# matrix-loop 玻璃化 + 实时飞轮 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 matrix-loop 前端改成「深色玻璃」设计语言（对齐 waoowaoo），并把飞轮页从聚合计数摆设改成逐账号实时监看面板（3-5s 轮询）。

**Architecture:** 前端 Vite+React+TS+Tailwind3.4：新增玻璃 CSS token + 共享玻璃组件，全站继承；飞轮用 `usePolling` 轮询两个新后端读接口。后端 FastAPI：仅新增/扩展读接口聚合已有数据（`flywheel_events`/`snapshots`/`evaluations`/`video_assets`），不重采、不加消息队列。

**Tech Stack:** React 18 + Vite + Tailwind 3.4 + ECharts；FastAPI + SQLAlchemy + pytest；vitest + RTL。

**视觉基准（source of truth）：** `.superpowers/brainstorm/47537-1784011218/content/flywheel-v2.html`（用户已通过的高保真样稿，玻璃 token/布局/状态色以它为准）。

**Spec:** `docs/superpowers/specs/2026-07-14-matrix-loop-glass-realtime-flywheel-design.md`

---

## 文件结构

**前端 (`frontend/src/`)**
- Create `styles/glass-tokens.css` — 玻璃设计 token（CSS 变量）
- Modify `tailwind.config.ts` — theme.extend 接入 token
- Modify `main.tsx` 或 `index.css` — import glass-tokens.css
- Create `components/GlassCard.tsx`、`GlassButton.tsx`、`StatusPill.tsx`、`StepTracker.tsx`、`AccountCard.tsx`、`EventFeed.tsx`
- Create `hooks/usePolling.ts`
- Create `charts/echartsGlassTheme.ts`
- Modify `api/client.ts`、`api/types.ts` — 新增飞轮接口/类型
- Rewrite `pages/Flywheel.tsx`
- Modify `pages/Video.tsx` 及其余页（Overview/Flow/Compare/ContentLibrary/AccountDetail）

**后端 (`backend/app/`)**
- Modify `orchestrator/state.py` — 新增 `flywheel_accounts()`、`flywheel_events_since()`、扩展 `flywheel_state()`
- Modify `api/routes.py` — 新增 `GET /flywheel/accounts`、`GET /flywheel/events`
- Test `backend/tests/test_flywheel_realtime.py`

---

## Phase A — 玻璃设计系统（基础）

### Task 1: 玻璃 token + Tailwind 接入

**Files:**
- Create: `frontend/src/styles/glass-tokens.css`
- Modify: `frontend/src/main.tsx`（加一行 import）
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: 写 glass-tokens.css**（值取自已通过样稿 flywheel-v2.html）

```css
/* frontend/src/styles/glass-tokens.css */
:root{
  --blue1:#2f7bff; --blue2:#5ca8ff;
  --cyan:#4CD4F0; --green:#38E08A; --amber:#FFB020; --red:#FF5C7A;
  --lime:#B6FF3C; --violet:#A78BFA;
  --txt:#EAF0FA; --muted:#93A0B8; --dim:#5C6579;
  --glass:linear-gradient(160deg, rgba(255,255,255,0.075), rgba(255,255,255,0.028));
  --stroke:rgba(255,255,255,0.10);
  --glass-shadow:0 24px 48px -18px rgba(0,0,0,0.55);
  --glass-inset:inset 0 1px 0 rgba(255,255,255,0.09);
  --radius-glass:20px;
}
body{
  background:
    radial-gradient(1100px 620px at 12% -8%, rgba(47,123,255,0.22), transparent 60%),
    radial-gradient(900px 560px at 108% 12%, rgba(167,139,250,0.16), transparent 58%),
    radial-gradient(700px 700px at 60% 120%, rgba(76,212,240,0.10), transparent 60%),
    #070b14;
  color:var(--txt);
}
.glass{
  background:var(--glass); border:1px solid var(--stroke); border-radius:var(--radius-glass);
  backdrop-filter:blur(22px) saturate(140%);
  box-shadow:var(--glass-shadow), var(--glass-inset);
}
@keyframes glasspulse{0%{box-shadow:0 0 0 0 rgba(76,212,240,0.55)}70%{box-shadow:0 0 0 7px rgba(76,212,240,0)}100%{box-shadow:0 0 0 0 rgba(76,212,240,0)}}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan);animation:glasspulse 1.8s infinite;}
```

- [ ] **Step 2: import 到入口**

在 `frontend/src/main.tsx` 顶部加：`import "./styles/glass-tokens.css";`（放在现有 css import 之后，使其覆盖）

- [ ] **Step 3: Tailwind 接入 token**

在 `frontend/tailwind.config.ts` 的 `theme.extend.colors` 里补充（与现有 BI 色并存，供 className 用）：

```ts
// 在 colors 里追加：
blue1: "#2f7bff", blue2: "#5ca8ff",
run: "#4CD4F0", ok: "#38E08A", block: "#FFB020", err: "#FF5C7A",
txt: "#EAF0FA", muted2: "#93A0B8", dim2: "#5C6579",
```

并在 `fontFamily` 里确保有：`sans: ["Inter", "Noto Sans SC", "sans-serif"], mono: ["JetBrains Mono", "monospace"]`（若字体未引入，在 `index.html` 加 Google Fonts link：Inter + JetBrains Mono）。

- [ ] **Step 4: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS/PostCSS 报错。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/glass-tokens.css frontend/src/main.tsx frontend/tailwind.config.ts frontend/index.html
git commit -m "feat(ui): add glass design tokens (direction B)"
```

### Task 2: 玻璃共享组件

**Files:**
- Create: `frontend/src/components/GlassCard.tsx`, `GlassButton.tsx`, `StatusPill.tsx`

- [ ] **Step 1: GlassCard**（替代 ChartCard，保留 `title`/`pill`/`children` API 便于旧页无痛替换）

```tsx
// frontend/src/components/GlassCard.tsx
import { ReactNode } from "react";
export function GlassCard({ title, pill, children, className = "" }:
  { title?: string; pill?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`glass p-4 ${className}`}>
      {(title || pill) && (
        <div className="flex items-center gap-2 mb-3">
          {title && <h3 className="text-[13px] font-semibold text-txt">{title}</h3>}
          {pill && <span className="ml-auto">{pill}</span>}
        </div>
      )}
      {children}
    </div>
  );
}
```

- [ ] **Step 2: GlassButton + StatusPill**

```tsx
// frontend/src/components/GlassButton.tsx
import { ButtonHTMLAttributes } from "react";
type V = "primary" | "secondary" | "ghost";
const V: Record<V, string> = {
  primary: "text-white bg-gradient-to-br from-blue1 to-blue2 shadow-[0_6px_16px_rgba(47,123,255,0.4)]",
  secondary: "bg-white/8 border border-white/12 text-txt",
  ghost: "bg-transparent text-muted2 hover:text-txt",
};
export function GlassButton({ variant = "secondary", className = "", ...p }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: V }) {
  return <button className={`rounded-xl px-4 py-2 text-[12.5px] font-medium transition ${V[variant]} ${className}`} {...p} />;
}
```

```tsx
// frontend/src/components/StatusPill.tsx
type S = "running" | "blocked" | "ok" | "error" | "idle";
const MAP: Record<S, { cls: string; label: string; dot: string }> = {
  running: { cls: "bg-run/14 text-run", label: "生成中", dot: "bg-run" },
  blocked: { cls: "bg-block/14 text-block", label: "待审核", dot: "bg-block" },
  ok:      { cls: "bg-ok/14 text-ok", label: "本轮完成", dot: "bg-ok" },
  error:   { cls: "bg-err/14 text-err", label: "报错", dot: "bg-err" },
  idle:    { cls: "bg-white/8 text-muted2", label: "待命", dot: "bg-muted2" },
};
export function StatusPill({ status, label }: { status: S; label?: string }) {
  const m = MAP[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold ${m.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />{label ?? m.label}
    </span>
  );
}
```

> 注：`bg-run/14` 等透明度类需 Tailwind 支持 `<color>/<alpha>`（3.4 支持）。若某色未在 config，用内联 `style` 兜底。

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npm run build`
Expected: 成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/GlassCard.tsx frontend/src/components/GlassButton.tsx frontend/src/components/StatusPill.tsx
git commit -m "feat(ui): glass shared components (card/button/status-pill)"
```

---

## Phase B — 实时飞轮后端（TDD）

### Task 3: 逐账号状态聚合 + GET /flywheel/accounts

**Files:**
- Modify: `backend/app/orchestrator/state.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_flywheel_realtime.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_flywheel_realtime.py
from datetime import datetime, timezone, timedelta
from app.orchestrator.state import flywheel_accounts

def _utc(): return datetime.now(timezone.utc)

def test_flywheel_accounts_running(session):
    from app.models import Account, FlywheelEvent
    a = Account(platform="tiktok", handle="@nina_web3", autopilot=True); session.add(a); session.flush()
    cid = "cyc1"
    for step, st in [("sync","ok"),("evaluate","ok"),("topic","ok"),("script","ok")]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id=cid, step=step, status=st))
    session.commit()
    rows = flywheel_accounts(session)
    row = next(r for r in rows if r["account_id"] == a.id)
    assert row["status"] == "running"
    assert row["current_step"] == "video"        # script 完成 → 下一步 video 在飞
    assert row["steps_done"] == 4
    assert row["handle"] == "@nina_web3"

def test_flywheel_accounts_blocked(session):
    from app.models import Account, FlywheelEvent
    a = Account(platform="twitter", handle="@xaue_gold", autopilot=True); session.add(a); session.flush()
    for step, st in [("sync","ok"),("evaluate","ok"),("topic","ok"),("script","ok"),("video","ok"),("approve","blocked")]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id="c2", step=step, status=st, detail="待人工审核"))
    session.commit()
    row = next(r for r in flywheel_accounts(session) if r["account_id"] == a.id)
    assert row["status"] == "blocked"
    assert row["current_step"] == "approve"
    assert row["blocked_reason"] == "待人工审核"

def test_flywheel_accounts_only_autopilot(session):
    from app.models import Account
    session.add(Account(platform="yt", handle="@manual", autopilot=False)); session.commit()
    assert all(r["handle"] != "@manual" for r in flywheel_accounts(session))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py -x -q`
Expected: FAIL（`flywheel_accounts` 不存在 / ImportError）。

- [ ] **Step 3: 实现 `flywheel_accounts`**（追加到 `backend/app/orchestrator/state.py`）

```python
# backend/app/orchestrator/state.py  (追加)
from datetime import datetime, timezone
from sqlalchemy import select, func

STEP_ORDER = ["sync", "evaluate", "topic", "script", "video", "approve", "publish", "track"]

def _derive_status(cycle_events):
    """从本轮事件推导 (status, current_step, step_index, steps_done, blocked_reason)。"""
    if not cycle_events:
        return "idle", STEP_ORDER[0], 0, 0, None
    last = cycle_events[-1]
    done = {e.step for e in cycle_events if e.status in ("ok", "skipped")}
    steps_done = sum(1 for s in STEP_ORDER if s in done)
    if last.status == "error":
        return "error", last.step, STEP_ORDER.index(last.step), steps_done, last.detail
    if last.status == "blocked":
        return "blocked", last.step, STEP_ORDER.index(last.step), steps_done, last.detail
    if last.step == STEP_ORDER[-1] and last.status in ("ok", "skipped"):
        return "ok", STEP_ORDER[-1], len(STEP_ORDER) - 1, steps_done, None
    # 正常推进：当前步 = 最后完成步的下一步
    idx = min(STEP_ORDER.index(last.step) + 1, len(STEP_ORDER) - 1)
    return "running", STEP_ORDER[idx], idx, steps_done, None

def flywheel_accounts(session) -> list[dict]:
    from app.models import Account, FlywheelEvent, Evaluation, Snapshot, VideoAsset
    from app.config import get_settings
    now = datetime.now(timezone.utc)
    interval_min = get_settings().orchestrator_interval_minutes
    out = []
    accts = session.scalars(
        select(Account).where(Account.autopilot.is_(True)).order_by(Account.id)
    ).all()
    for a in accts:
        last_ev = session.scalars(
            select(FlywheelEvent).where(FlywheelEvent.account_id == a.id)
            .order_by(FlywheelEvent.id.desc()).limit(1)
        ).first()
        cycle_events = []
        if last_ev and last_ev.cycle_id:
            cycle_events = session.scalars(
                select(FlywheelEvent).where(
                    FlywheelEvent.account_id == a.id,
                    FlywheelEvent.cycle_id == last_ev.cycle_id,
                ).order_by(FlywheelEvent.id.asc())
            ).all()
        status, current_step, step_index, steps_done, blocked_reason = _derive_status(cycle_events)
        elapsed = int((now - last_ev.ts).total_seconds()) if last_ev else None

        snaps = session.scalars(
            select(Snapshot).where(Snapshot.account_id == a.id).order_by(Snapshot.ts.desc()).limit(2)
        ).all()
        latest, prev = (snaps[0] if snaps else None), (snaps[1] if len(snaps) > 1 else None)
        fol_delta = None
        if latest and prev and prev.followers:
            fol_delta = round((latest.followers - prev.followers) / prev.followers * 100, 1)

        ev = session.scalars(
            select(Evaluation).where(Evaluation.account_id == a.id).order_by(Evaluation.id.desc()).limit(1)
        ).first()

        cost_cycle = 0.0
        if last_ev:
            cost_cycle = float(session.scalar(
                select(func.coalesce(func.sum(VideoAsset.cost), 0.0))
                .where(VideoAsset.account_id == a.id, VideoAsset.created_at >= cycle_events[0].ts)
            ) or 0.0) if cycle_events else 0.0

        next_eta = None
        if status in ("ok", "idle") and last_ev:
            next_eta = max(0, int(interval_min * 60 - (now - last_ev.ts).total_seconds()))

        out.append({
            "account_id": a.id, "platform": a.platform, "handle": a.handle, "autopilot": a.autopilot,
            "status": status, "current_step": current_step, "step_index": step_index,
            "steps_done": steps_done, "elapsed_sec": elapsed, "blocked_reason": blocked_reason,
            "last_event": ({"step": last_ev.step, "status": last_ev.status,
                            "detail": last_ev.detail, "ts": last_ev.ts.isoformat()} if last_ev else None),
            "kpis": {"followers": latest.followers if latest else None,
                     "followers_delta": fol_delta,
                     "views_7d": latest.views if latest else None,
                     "score": round(ev.composite_score) if ev else None},
            "cost_cycle": round(cost_cycle, 2),
            "next_run_eta_sec": next_eta,
            "synced_at": latest.ts.isoformat() if latest else None,
        })
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py -x -q`
Expected: 3 passed。

- [ ] **Step 5: 加路由**（`backend/app/api/routes.py`，在 `/flywheel/status` 附近）

```python
from app.orchestrator.state import flywheel_accounts  # 加到顶部现有 state 导入

@router.get("/flywheel/accounts")
def flywheel_accounts_route(db: Session = Depends(get_db)) -> list[dict]:
    return flywheel_accounts(db)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/state.py backend/app/api/routes.py backend/tests/test_flywheel_realtime.py
git commit -m "feat(flywheel): per-account live status endpoint"
```

### Task 4: 事件增量 GET /flywheel/events

**Files:**
- Modify: `backend/app/orchestrator/state.py`, `backend/app/api/routes.py`
- Test: `backend/tests/test_flywheel_realtime.py`

- [ ] **Step 1: 追加失败测试**

```python
def test_flywheel_events_since_and_filter(session):
    from app.models import Account, FlywheelEvent
    from app.orchestrator.state import flywheel_events_since
    a = Account(platform="tiktok", handle="@n", autopilot=True); session.add(a); session.flush()
    for step in ["sync", "evaluate", "topic"]:
        session.add(FlywheelEvent(account_id=a.id, cycle_id="c", step=step, status="ok"))
    session.commit()
    all_ev = flywheel_events_since(session, since_id=None, account_id=None, limit=50)
    assert len(all_ev) == 3
    assert all_ev[0]["account_handle"] == "@n"      # 带账号上下文
    max_id = max(e["id"] for e in all_ev)
    assert flywheel_events_since(session, since_id=max_id, account_id=None, limit=50) == []  # 增量为空
    assert len(flywheel_events_since(session, since_id=None, account_id=a.id, limit=50)) == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py::test_flywheel_events_since_and_filter -x -q`
Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现**

```python
# backend/app/orchestrator/state.py (追加)
def flywheel_events_since(session, *, since_id=None, account_id=None, limit=50) -> list[dict]:
    from app.models import FlywheelEvent, Account
    stmt = select(FlywheelEvent, Account.handle).join(
        Account, Account.id == FlywheelEvent.account_id, isouter=True
    )
    if since_id is not None:
        stmt = stmt.where(FlywheelEvent.id > since_id)
    if account_id is not None:
        stmt = stmt.where(FlywheelEvent.account_id == account_id)
    stmt = stmt.order_by(FlywheelEvent.id.asc()).limit(limit)
    rows = session.execute(stmt).all()
    return [{"id": e.id, "account_id": e.account_id, "account_handle": handle,
             "step": e.step, "status": e.status, "detail": e.detail,
             "ts": e.ts.isoformat()} for (e, handle) in rows]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py -x -q`
Expected: 全部 passed。

- [ ] **Step 5: 加路由**

```python
# backend/app/api/routes.py
from app.orchestrator.state import flywheel_events_since  # 顶部导入

@router.get("/flywheel/events")
def flywheel_events_route(since_id: int | None = None, account_id: int | None = None,
                          limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return flywheel_events_since(db, since_id=since_id, account_id=account_id, limit=min(limit, 200))
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/state.py backend/app/api/routes.py backend/tests/test_flywheel_realtime.py
git commit -m "feat(flywheel): incremental events endpoint"
```

### Task 5: 扩展 /flywheel（今日成本 + 全局状态计数）

**Files:** Modify `backend/app/orchestrator/state.py`, Test `backend/tests/test_flywheel_realtime.py`

- [ ] **Step 1: 追加失败测试**

```python
def test_flywheel_state_has_today_cost_and_counts(session):
    from app.models import Account, VideoAsset
    from app.orchestrator.state import flywheel_state
    a = Account(platform="tiktok", handle="@n", autopilot=True); session.add(a); session.flush()
    session.add(VideoAsset(account_id=a.id, provider="faceless", cost=0.42, status="ready"))
    session.commit()
    st = flywheel_state(session)
    assert "today_cost" in st and st["today_cost"] >= 0.42
    assert "status_counts" in st  # {running, blocked, ok, ...}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py::test_flywheel_state_has_today_cost_and_counts -x -q`
Expected: FAIL（KeyError today_cost）。

- [ ] **Step 3: 扩展 `flywheel_state()`**（在其 `return {...}` 前插入，并把新键并入返回 dict）

```python
    # ---- 追加：今日成本 + 全局状态计数 ----
    from datetime import datetime, timezone
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_cost = float(session.scalar(
        _select(func.coalesce(func.sum(VideoAsset.cost), 0.0)).where(VideoAsset.created_at >= day_start)
    ) or 0.0)
    status_counts: dict[str, int] = {}
    for row in flywheel_accounts(session):
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
```

在返回 dict 里追加：`"today_cost": round(today_cost, 2), "status_counts": status_counts,`

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_flywheel_realtime.py -q`
Expected: 全部 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/state.py backend/tests/test_flywheel_realtime.py
git commit -m "feat(flywheel): today_cost + status_counts in /flywheel"
```

---

## Phase C — 实时飞轮前端

### Task 6: usePolling hook + API/类型

**Files:**
- Create: `frontend/src/hooks/usePolling.ts`
- Test: `frontend/src/hooks/usePolling.test.ts`
- Modify: `frontend/src/api/client.ts`, `frontend/src/api/types.ts`

- [ ] **Step 1: 写失败测试**

```ts
// frontend/src/hooks/usePolling.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { usePolling } from "./usePolling";

describe("usePolling", () => {
  it("calls fn immediately then on interval", async () => {
    vi.useFakeTimers();
    const fn = vi.fn().mockResolvedValue(1);
    renderHook(() => usePolling(fn, 3000));
    expect(fn).toHaveBeenCalledTimes(1);       // 立即拉一次
    await vi.advanceTimersByTimeAsync(3000);
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/hooks/usePolling.test.ts`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 usePolling**

```ts
// frontend/src/hooks/usePolling.ts
import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(fn: () => Promise<T>, intervalMs = 4000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn); fnRef.current = fn;

  const run = useCallback(() => {
    fnRef.current().then(setData).catch((e) => setError(String(e))).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    run();
    let id = window.setInterval(() => { if (!document.hidden) run(); }, intervalMs);
    const onVis = () => { if (!document.hidden) run(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { window.clearInterval(id); document.removeEventListener("visibilitychange", onVis); };
  }, [run, intervalMs]);

  return { data, error, loading, reload: run };
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/hooks/usePolling.test.ts`
Expected: PASS。

- [ ] **Step 5: 加 API + 类型**

`frontend/src/api/types.ts` 追加：

```ts
export interface FlywheelAccountLive {
  account_id: number; platform: string; handle: string; autopilot: boolean;
  status: "running" | "blocked" | "ok" | "error" | "idle";
  current_step: string; step_index: number; steps_done: number;
  elapsed_sec: number | null; blocked_reason: string | null;
  last_event: { step: string; status: string; detail: string | null; ts: string } | null;
  kpis: { followers: number | null; followers_delta: number | null; views_7d: number | null; score: number | null };
  cost_cycle: number; next_run_eta_sec: number | null; synced_at: string | null;
}
export interface FlywheelEventLive {
  id: number; account_id: number | null; account_handle: string | null;
  step: string; status: string; detail: string | null; ts: string;
}
```

`frontend/src/api/client.ts` 的 `api` 对象里追加：

```ts
  getFlywheelAccounts: () => req<FlywheelAccountLive[]>("/flywheel/accounts"),
  getFlywheelEvents: (sinceId?: number) =>
    req<FlywheelEventLive[]>(`/flywheel/events${sinceId ? `?since_id=${sinceId}` : ""}`),
```

（记得在 client.ts / types.ts 顶部 import/export 新类型。）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/usePolling.ts frontend/src/hooks/usePolling.test.ts frontend/src/api/client.ts frontend/src/api/types.ts
git commit -m "feat(flywheel): usePolling hook + live flywheel api"
```

### Task 7: StepTracker 组件（TDD）

**Files:** Create `frontend/src/components/StepTracker.tsx`, Test `frontend/src/components/StepTracker.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
// frontend/src/components/StepTracker.test.tsx
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StepTracker, segState } from "./StepTracker";

describe("StepTracker", () => {
  it("maps step index to done/active/upcoming", () => {
    expect(segState(0, 4, "running")).toBe("done");   // 已过
    expect(segState(4, 4, "running")).toBe("active");  // 当前
    expect(segState(6, 4, "running")).toBe("upcoming");
    expect(segState(5, 5, "blocked")).toBe("warn");    // 卡住步
  });
  it("renders 8 steps", () => {
    const { container } = render(<StepTracker stepIndex={4} status="running" />);
    expect(container.querySelectorAll("[data-step]").length).toBe(8);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/components/StepTracker.test.tsx`
Expected: FAIL。

- [ ] **Step 3: 实现**（视觉：珠子+渐变连线，class 见样稿 flywheel-v2.html 的 `.track/.seg/.bead`）

```tsx
// frontend/src/components/StepTracker.tsx
export const STEPS = ["sync","evaluate","topic","script","video","approve","publish","track"];
export type SegState = "done" | "active" | "upcoming" | "warn";

export function segState(i: number, stepIndex: number, status: string): SegState {
  if ((status === "blocked" || status === "error") && i === stepIndex) return "warn";
  if (i < stepIndex) return "done";
  if (i === stepIndex) return "active";
  return "upcoming";
}
const SEG: Record<SegState, string> = {
  done: "bg-gradient-to-r from-ok to-[#2fbf78]",
  active: "bg-gradient-to-r from-run to-blue2 shadow-[0_0_10px_rgba(76,212,240,0.5)]",
  upcoming: "bg-white/10",
  warn: "bg-block",
};
export function StepTracker({ stepIndex, status }: { stepIndex: number; status: string }) {
  return (
    <div>
      <div className="flex items-center">
        {STEPS.map((s, i) => (
          <div key={s} data-step={s} className="flex items-center flex-1 last:flex-none">
            <span className={`w-2 h-2 rounded-full -mx-px z-10 ${
              segState(i, stepIndex, status) === "upcoming" ? "bg-white/15" :
              segState(i, stepIndex, status) === "warn" ? "bg-block" :
              segState(i, stepIndex, status) === "active" ? "bg-run shadow-[0_0_0_4px_rgba(76,212,240,0.18)]" : "bg-ok"}`} />
            {i < STEPS.length - 1 && <span className={`h-[3px] flex-1 rounded ${SEG[segState(i, stepIndex, status)]}`} />}
          </div>
        ))}
      </div>
      <div className="flex justify-between text-[9px] text-dim2 mt-1.5 px-0.5">
        {STEPS.map((s, i) => <span key={s} className={i === stepIndex ? "text-run font-semibold" : ""}>{s}</span>)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/components/StepTracker.test.tsx`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StepTracker.tsx frontend/src/components/StepTracker.test.tsx
git commit -m "feat(flywheel): StepTracker component"
```

### Task 8: AccountCard + EventFeed 组件

**Files:** Create `frontend/src/components/AccountCard.tsx`, `EventFeed.tsx`, Test `frontend/src/components/AccountCard.test.tsx`

- [ ] **Step 1: 写失败测试**（三态渲染 + 字段展示）

```tsx
// frontend/src/components/AccountCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AccountCard } from "./AccountCard";
import type { FlywheelAccountLive } from "../api/types";

const base: FlywheelAccountLive = {
  account_id: 1, platform: "tiktok", handle: "@nina_web3", autopilot: true,
  status: "running", current_step: "video", step_index: 4, steps_done: 4,
  elapsed_sec: 102, blocked_reason: null,
  last_event: { step: "script", status: "ok", detail: null, ts: new Date().toISOString() },
  kpis: { followers: 12400, followers_delta: 2.1, views_7d: 86200, score: 78 },
  cost_cycle: 0.42, next_run_eta_sec: null, synced_at: new Date().toISOString(),
};

describe("AccountCard", () => {
  it("running shows handle, cost, platform", () => {
    render(<AccountCard a={base} />);
    expect(screen.getByText("@nina_web3")).toBeTruthy();
    expect(screen.getByText(/\$0.42/)).toBeTruthy();
    expect(screen.getByText(/TikTok/i)).toBeTruthy();
  });
  it("blocked shows action banner + reason", () => {
    render(<AccountCard a={{ ...base, status: "blocked", current_step: "approve", step_index: 5, blocked_reason: "待人工审核" }} />);
    expect(screen.getByText(/待人工审核/)).toBeTruthy();
  });
  it("ok shows next-run countdown", () => {
    render(<AccountCard a={{ ...base, status: "ok", next_run_eta_sec: 724 }} />);
    expect(screen.getByText(/下一轮/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/components/AccountCard.test.tsx`
Expected: FAIL。

- [ ] **Step 3: 实现 AccountCard + EventFeed**（视觉严格照样稿 flywheel-v2.html 的 `.card/.chead/.metrics/.banner/.mini` 与 `.feed/.ev`；平台图标映射 tiktok→♪ / twitter→𝕏 / youtube→▶ / instagram→✦）。含：头像、handle、平台芯片、`StatusPill`、已用时或卡住时长、`StepTracker`、指标条(粉丝+涨幅/播放/综合分/本轮成本 `$${a.cost_cycle}`/下一轮倒计时/同步新鲜度)、blocked 行动条。ok 态渲染折叠 `.mini` 行含 `下一轮 mm:ss`。

```tsx
// frontend/src/components/AccountCard.tsx  —— 骨架，样式类照样稿
import type { FlywheelAccountLive } from "../api/types";
import { StatusPill } from "./StatusPill";
import { StepTracker } from "./StepTracker";

const PLAT: Record<string, string> = { tiktok: "♪ TikTok", twitter: "𝕏 Twitter", youtube: "▶ YouTube", instagram: "✦ Instagram" };
const fmtDur = (s: number | null) => s == null ? "—" : `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;

export function AccountCard({ a }: { a: FlywheelAccountLive }) {
  const plat = PLAT[a.platform] ?? a.platform;
  if (a.status === "ok" || a.status === "idle") {
    return (
      <div className="glass flex items-center gap-3 px-4 py-3">
        <span className="font-semibold text-[14px]">{a.handle}</span>
        <span className="text-[10.5px] text-muted2 border border-white/10 rounded-lg px-2 py-0.5">{plat}</span>
        <StatusPill status={a.status} />
        <span className="ml-auto flex gap-4 items-center text-[11.5px] text-muted2">
          <span>综合分 <b className="text-lime">{a.kpis.score ?? "—"}</b></span>
          <span>本轮 <b className="text-lime">${a.cost_cycle}</b></span>
          <span className="font-mono">下一轮 {fmtDur(a.next_run_eta_sec)}</span>
        </span>
      </div>
    );
  }
  return (
    <div className={`glass p-[18px] ${a.status === "running" ? "border-run/34" : a.status === "blocked" ? "border-block/34" : "border-err/34"}`}>
      <div className="flex items-center gap-2.5 mb-3.5">
        <span className="font-semibold text-[14px]">{a.handle}</span>
        <span className="text-[10.5px] text-muted2 border border-white/10 rounded-lg px-2 py-0.5">{plat}</span>
        <StatusPill status={a.status} label={a.blocked_reason ? "待人工审核" : undefined} />
        <span className="ml-auto font-mono text-[11.5px] text-muted2 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1">
          ⏱ {a.status === "blocked" ? `卡 ${fmtDur(a.elapsed_sec)}` : fmtDur(a.elapsed_sec)}
        </span>
      </div>
      <StepTracker stepIndex={a.step_index} status={a.status} />
      <div className="flex items-end gap-5 mt-3.5 text-[11px]">
        <div><div className="text-muted2">粉丝</div><div className="font-bold text-[14px]">{(a.kpis.followers ?? 0).toLocaleString()} {a.kpis.followers_delta != null && <small className="text-ok">▲{a.kpis.followers_delta}%</small>}</div></div>
        <div><div className="text-muted2">近7日播放</div><div className="font-bold text-[14px]">{(a.kpis.views_7d ?? 0).toLocaleString()}</div></div>
        <div><div className="text-muted2">综合分</div><div className="font-bold text-[14px] text-lime">{a.kpis.score ?? "—"}</div></div>
        <div><div className="text-muted2">本轮成本</div><div className="font-bold text-[14px] text-lime">${a.cost_cycle}</div></div>
        <div className="ml-auto text-right"><div className="text-muted2">数据同步</div><div className="text-muted2 text-[12px]">{a.synced_at ? new Date(a.synced_at).toLocaleTimeString() : "—"}</div></div>
      </div>
      {a.status === "blocked" && (
        <div className="mt-3 text-[11.5px] text-block bg-block/8 border border-block/20 rounded-xl px-3 py-2 flex items-center gap-2">
          ⏸ {a.blocked_reason ?? "等待处理"} · 卡在 {a.current_step} 步
          <a href="/video" className="ml-auto underline cursor-pointer">→ 去成片审核</a>
        </div>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/EventFeed.tsx —— 样式照样稿 .feed/.ev/.ei
import type { FlywheelEventLive } from "../api/types";
const ICON: Record<string, { c: string; g: string }> = {
  ok: { c: "text-ok bg-ok/16", g: "✓" }, blocked: { c: "text-block bg-block/16", g: "⚠" },
  error: { c: "text-err bg-err/16", g: "✕" }, running: { c: "text-run bg-run/16", g: "▶" },
};
export function EventFeed({ events }: { events: FlywheelEventLive[] }) {
  return (
    <aside className="glass p-4 self-start">
      <h4 className="text-[13px] font-semibold flex items-center gap-2 mb-3.5">实时事件流 <span className="live-dot" /></h4>
      {events.map((e) => {
        const ic = ICON[e.status] ?? ICON.running;
        return (
          <div key={e.id} className="flex gap-2.5 py-2 border-b border-white/5 last:border-0">
            <span className={`w-[18px] h-[18px] rounded-md flex items-center justify-center text-[10px] mt-0.5 ${ic.c}`}>{ic.g}</span>
            <div className="text-[11.5px]"><b>{e.account_handle ?? "—"}</b> · {e.step} {e.detail ?? e.status}
              <div className="text-dim2 text-[10px] font-mono mt-0.5">{new Date(e.ts).toLocaleTimeString()}</div></div>
          </div>
        );
      })}
    </aside>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/components/AccountCard.test.tsx`
Expected: PASS（若断言文案与实现不符，微调断言/文案使一致）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AccountCard.tsx frontend/src/components/EventFeed.tsx frontend/src/components/AccountCard.test.tsx
git commit -m "feat(flywheel): AccountCard + EventFeed components"
```

### Task 9: 重写 Flywheel.tsx

**Files:** Rewrite `frontend/src/pages/Flywheel.tsx`

- [ ] **Step 1: 重写页面**（用 `usePolling` 拉 `getFlywheelAccounts` + `getFlywheel`；顶栏玻璃 pill 含 LIVE 脉冲/今日成片/今日成本/自驾数/待审/暂停；两栏 = AccountCard 列 + EventFeed。布局/类照样稿 flywheel-v2.html）

```tsx
// frontend/src/pages/Flywheel.tsx
import { usePolling } from "../hooks/usePolling";
import { api } from "../api/client";
import { AccountCard } from "../components/AccountCard";
import { EventFeed } from "../components/EventFeed";
import { GlassButton } from "../components/GlassButton";

export function Flywheel() {
  const accts = usePolling(() => api.getFlywheelAccounts(), 4000);
  const state = usePolling(() => api.getFlywheel(), 4000);
  const evs = usePolling(() => api.getFlywheelEvents(), 4000);
  const s = state.data;
  return (
    <div className="max-w-[1120px] mx-auto">
      <header className="glass flex items-center gap-3.5 px-5 py-3.5 rounded-[22px] mb-4.5">
        <div className="w-[34px] h-[34px] rounded-[11px] bg-gradient-to-br from-blue1 to-blue2 grid place-items-center font-extrabold">◎</div>
        <div className="text-[17px] font-bold">自动驾驶飞轮</div>
        <span className="inline-flex items-center gap-1.5 bg-run/12 text-run border border-run/30 rounded-full px-2.5 py-1 text-[11px] font-semibold">
          <span className="live-dot" />实时 · 4s
        </span>
        <div className="ml-auto flex gap-5.5 items-center text-[12px] text-muted2">
          <span>今日成片 <b className="text-txt">{s?.videos_today ?? "—"}</b></span>
          <span>今日成本 <b className="text-txt">${s?.today_cost ?? "0"}</b></span>
          <span>自驾账号 <b className="text-txt">{s?.autopilot_accounts ?? "—"}</b></span>
          <span>待审 <b className="text-block">{s?.pending_review ?? 0}</b></span>
          <GlassButton onClick={() => { /* 复用现有 pause/resume: api.pauseFlywheel?.() 后 state.reload() */ }}>
            {s?.paused ? "▶ 恢复" : "⏸ 暂停"}
          </GlassButton>
        </div>
      </header>
      <div className="grid grid-cols-[1fr_300px] gap-4">
        <div className="flex flex-col gap-3.5">
          {(accts.data ?? []).map((a) => <AccountCard key={a.account_id} a={a} />)}
          {accts.data?.length === 0 && <div className="glass p-6 text-center text-muted2">暂无自动驾驶账号</div>}
        </div>
        <EventFeed events={evs.data ?? []} />
      </div>
    </div>
  );
}
```

> 注：`videos_today` 若 `/flywheel` 未返回，用 `s?.status_counts` 或补后端字段；pause/resume 复用现有 `/flywheel/pause`、`/flywheel/resume`（client.ts 里若无则按现有 Flywheel.tsx 的调用补上）。保留旧的 9 步环形图可选：如需，放在账号列上方用 GlassCard 包裹。

- [ ] **Step 2: 手动验证**

Run: `cd frontend && npm run dev`（另开后端 `cd backend && .venv/bin/uvicorn app.main:app --reload`），浏览器开 `/`，确认：账号活卡片渲染、每 4s 刷新、事件流更新、成本/平台/倒计时可见、深色玻璃观感。
Expected: 与样稿一致、数据实时。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Flywheel.tsx
git commit -m "feat(flywheel): real-time glass flywheel page"
```

---

## Phase D — 其余页面玻璃化

### Task 10: ECharts 深色玻璃主题

**Files:** Create `frontend/src/charts/echartsGlassTheme.ts`, Modify 图表组件注册主题

- [ ] **Step 1: 写主题**

```ts
// frontend/src/charts/echartsGlassTheme.ts
import * as echarts from "echarts";
export const GLASS_THEME = "glass";
echarts.registerTheme(GLASS_THEME, {
  backgroundColor: "transparent",
  color: ["#4CD4F0", "#B6FF3C", "#A78BFA", "#FF6FB5", "#38E08A", "#FFB020"],
  textStyle: { color: "#93A0B8", fontFamily: "Inter" },
  title: { textStyle: { color: "#EAF0FA" } },
  legend: { textStyle: { color: "#93A0B8" } },
  grid: { borderColor: "rgba(255,255,255,0.08)" },
  categoryAxis: { axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } } },
  valueAxis: { axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } } },
});
```

- [ ] **Step 2: 各 ECharts 组件启用主题**：在图表初始化处（`echarts-for-react` 的 `<ReactECharts theme="glass" .../>`，并 import 一次该文件注册）。逐个改 `FlywheelChart/ScoreRadar/SankeyChart/TrendChart` 等。

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npm run build` → 成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/charts/echartsGlassTheme.ts frontend/src/components/*.tsx
git commit -m "feat(ui): echarts dark-glass theme"
```

### Task 11: Video.tsx 玻璃化

**Files:** Modify `frontend/src/pages/Video.tsx`

- [ ] **Step 1: 替换容器/按钮为玻璃组件**：将 `ChartCard` → `GlassCard`，动作按钮 → `GlassButton`（生成=primary 蓝渐变、审核动作用 tone），草稿 kind/status 用 `StatusPill`/`GlassChip`。保持所有 api 调用与业务逻辑不变，仅换外观类。
- [ ] **Step 2: 手动验证** `/video` 观感与飞轮一致、功能不回归（生成脚本/生成视频/审核/发布按钮可用）。
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Video.tsx
git commit -m "feat(ui): glass-align video workbench"
```

### Task 12: 其余页面玻璃化

**Files:** Modify `frontend/src/pages/Overview.tsx`, `Flow.tsx`, `Compare.tsx`, `ContentLibrary.tsx`, `AccountDetail.tsx`, `components/Layout.tsx`

- [ ] **Step 1: Layout 顶栏 → 玻璃 pill 导航**（`Layout.tsx`：sticky header 用 `.glass` + 圆角 pill，激活项蓝渐变下划线/底色）。
- [ ] **Step 2: 逐页把 `ChartCard`→`GlassCard`、按钮→`GlassButton`、状态标签→`StatusPill`**（纯外观替换，不动数据逻辑）。ECharts 已在 Task 10 套主题。
- [ ] **Step 3: 全站构建 + 冒烟**

Run: `cd frontend && npm run build && npx vitest run`
Expected: 构建成功、既有测试 + 新测试全绿。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/*.tsx frontend/src/components/Layout.tsx
git commit -m "feat(ui): glass-align remaining pages + nav"
```

---

## Self-Review 记录

- **Spec 覆盖**：设计系统(T1-2) / 后端两端点+扩展(T3-5) / 前端轮询+组件+重写飞轮(T6-9) / ECharts主题(T10) / 视频工作台(T11) / 其余页+导航(T12) / 测试(散落各 TDD 任务)。✅ 全覆盖。
- **类型一致**：`FlywheelAccountLive`/`FlywheelEventLive`（T6）在 T8/T9 一致使用；`segState`/`STEPS`（T7）供 T8 用；后端 `flywheel_accounts`/`flywheel_events_since`（T3/T4）被 T5 与路由复用。✅
- **占位符**：视觉任务以「照样稿 flywheel-v2.html 的具体 class」为准（真实产物，非占位）；逻辑任务均给完整代码。✅
- **已知需执行时确认点**：`/flywheel` 是否已有 `videos_today` 字段（无则 T9 用 status_counts 或 T5 顺带补）；pause/resume 复用现有路由。
