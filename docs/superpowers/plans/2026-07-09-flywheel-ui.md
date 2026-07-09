# Flywheel UI (React) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the approved flywheel command-center as the app home (`/`): a live, spinning 9-step flywheel driven by `GET /flywheel`, with per-account autopilot toggles, a durable kill-switch (pause/resume), a KPI strip, and an activity feed — matching `frontend/design/flywheel-mockup.html` and consolidating the IA around the flywheel.

**Architecture:** A `FlywheelChart` presentational component (SVG ring + 9 angle-positioned nodes with custom line icons, CSS-animated spin/flow/pulse) driven by the `steps` array from `GET /flywheel`. A `Flywheel` page composes it with a KPI strip, an autopilot account rail (toggles → `POST /accounts/{id}/autopilot`), an activity feed (from `events`), and a pause control (→ `POST /flywheel/pause|resume`). `/` routes to `Flywheel`; the old Overview moves to `/overview`; the nav leads with 飞轮. Reuses the existing Tailwind design tokens (`bg/panel/line/lime/cyan/violet/pink/...`, `font-display/font-mono`). Keyframes added to `index.css`.

**Tech Stack:** Vite + React 18 + TS + Tailwind; vitest + @testing-library/react. Run from `frontend/`. Visual source of truth: `frontend/design/flywheel-mockup.html`.

Preconditions: on `main`, clean, `git checkout -b feat/flywheel-ui`. Baseline: `cd frontend && npx vitest run` → 38 pass; `npx tsc --noEmit` clean. Backend on :8010 serves `/flywheel`. Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- `frontend/src/api/types.ts` (modify) — `FlywheelStep`, `FlywheelAccount`, `FlywheelEventOut`, `FlywheelState`.
- `frontend/src/api/client.ts` (modify) — `getFlywheel`, `setAutopilot`, `pauseFlywheel`, `resumeFlywheel`, `flywheelStatus`.
- `frontend/src/index.css` (modify) — flywheel keyframes (spin/dash/pop) + node color vars.
- `frontend/src/components/FlywheelChart.tsx` (create) — the animated ring.
- `frontend/src/pages/Flywheel.tsx` (create) — the home page.
- `frontend/src/App.tsx` (modify) — `/` → Flywheel, `/overview` → Overview.
- `frontend/src/components/Layout.tsx` (modify) — nav leads with 飞轮 + a pause/status control.
- Tests: `frontend/src/pages/Flywheel.test.tsx` (create).

---

### Task 1: Types + API client

- [ ] **Step 1: Add types** to `frontend/src/api/types.ts`:

```ts
// ---- Flywheel ----
export interface FlywheelStep { key: string; label: string; count: number; status: string; }
export interface FlywheelAccount { id: number; handle: string; platform: string; autopilot: boolean; }
export interface FlywheelEventOut { account_id: number | null; step: string; status: string; detail: string | null; ts: string | null; }
export interface FlywheelState {
  paused: boolean;
  autopilot_accounts: number;
  pending_review: number;
  steps: FlywheelStep[];
  accounts: FlywheelAccount[];
  events: FlywheelEventOut[];
}
```

- [ ] **Step 2: Add client methods** to `frontend/src/api/client.ts` (import the new types), in the `api` object:

```ts
  // ---- Flywheel ----
  getFlywheel: () => req<FlywheelState>("/flywheel"),
  flywheelStatus: () => req<{ paused: boolean }>("/flywheel/status"),
  pauseFlywheel: () => req<{ paused: boolean }>("/flywheel/pause", { method: "POST" }),
  resumeFlywheel: () => req<{ paused: boolean }>("/flywheel/resume", { method: "POST" }),
  setAutopilot: (accountId: number, enabled: boolean) =>
    req<{ account_id: number; autopilot: boolean }>(`/accounts/${accountId}/autopilot`, {
      method: "POST", body: JSON.stringify({ enabled }),
    }),
```

- [ ] **Step 3: Typecheck** `cd frontend && npx tsc --noEmit` → exit 0.

- [ ] **Step 4: Commit** `git add frontend/src/api/types.ts frontend/src/api/client.ts` + commit `feat(fe): flywheel API client + types`.

---

### Task 2: Flywheel keyframes in index.css

- [ ] **Step 1: Append to `frontend/src/index.css`** (these mirror the mockup):

```css
/* ---- Flywheel animations ---- */
@keyframes fw-spin { to { transform: rotate(360deg); } }
@keyframes fw-dash { to { stroke-dashoffset: -44; } }
@keyframes fw-pop {
  0%, 100% { box-shadow: 0 0 12px color-mix(in oklab, var(--nc) 14%, transparent); }
  50% { box-shadow: 0 0 30px color-mix(in oklab, var(--nc) 38%, transparent); }
}
.fw-sweep { transform-origin: center; animation: fw-spin 14s linear infinite; }
.fw-flow { animation: fw-dash 2.4s linear infinite; }
.fw-core-glow { animation: fw-spin 8s linear infinite; }
.fw-node-on { animation: fw-pop 3.8s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .fw-sweep, .fw-flow, .fw-core-glow, .fw-node-on { animation: none; }
}
```

- [ ] **Step 2: Commit** `git add frontend/src/index.css` + commit `feat(fe): flywheel keyframes`.

---

### Task 3: `FlywheelChart` component

**Files:** Create `frontend/src/components/FlywheelChart.tsx`; Test covered by the page test in Task 6.

- [ ] **Step 1: Implement** `frontend/src/components/FlywheelChart.tsx` — port the mockup's ring. Drive nodes from the `steps` prop; a node is "on" when `status === "ok"`. Use the 9 custom SVG icons + per-key colors from the mockup.

```tsx
import type { FlywheelStep } from "../api/types";

const NC: Record<string, string> = {
  crawl: "var(--pink,#FF6FB5)", brief: "var(--violet,#A78BFA)", script: "var(--cyan,#4CD4F0)",
  video: "var(--cyan,#4CD4F0)", publish: "var(--lime,#B6FF3C)", track: "var(--cyan,#4CD4F0)",
  retro: "var(--violet,#A78BFA)", evaluate: "var(--violet,#A78BFA)", improve: "var(--lime,#B6FF3C)",
};

// custom line icons (24x24) keyed by step
const ICON: Record<string, JSX.Element> = {
  crawl: <><path d="M12 22a7 7 0 0 0 7-7c0-3-2-5.2-3.6-7.6C14 5.2 13 3.6 12 2c-.6 3-2 4.6-3.4 6.1C7 10.2 5 12 5 15a7 7 0 0 0 7 7z"/><path d="M12 22a3.3 3.3 0 0 0 3.3-3.3c0-1.8-1.7-3.1-3.3-5-1.6 1.9-3.3 3.2-3.3 5A3.3 3.3 0 0 0 12 22z"/></>,
  brief: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.6"/><circle cx="12" cy="12" r="1.1"/></>,
  script: <><path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4"/><path d="M10 8.5h3M10 12h6M10 15.5h6"/></>,
  video: <><rect x="3" y="6" width="12.5" height="12" rx="2.5"/><path d="M15.5 10.2l5.5-2.7v9l-5.5-2.7z"/></>,
  publish: <><path d="M21.5 3L2.6 10.2l7.3 2.9 2.9 7.3z"/><path d="M21.5 3L9.9 13.1"/></>,
  track: <path d="M3 12h3.4l2.4-6 4 13 2.5-7H21"/>,
  retro: <><path d="M20 12a8 8 0 0 1-13.7 5.6"/><path d="M4 12A8 8 0 0 1 17.7 6.4"/><path d="M17.7 2.6v3.8h-3.8"/><path d="M6.3 21.4v-3.8h3.8"/></>,
  evaluate: <><path d="M4 20h16"/><rect x="5.4" y="12" width="3.2" height="6" rx="1"/><rect x="10.4" y="7" width="3.2" height="11" rx="1"/><rect x="15.4" y="10" width="3.2" height="8" rx="1"/></>,
  improve: <><path d="M9.6 18.5h4.8M10.1 21.5h3.8"/><path d="M12 2.5A6.2 6.2 0 0 0 8.2 13.6c.9.7 1.3 1.4 1.3 2.4h5c0-1 .4-1.7 1.3-2.4A6.2 6.2 0 0 0 12 2.5z"/></>,
};

export function FlywheelChart({ steps, deliveredToday, autopilotCount, paused }:
  { steps: FlywheelStep[]; deliveredToday: number; autopilotCount: number; paused: boolean }) {
  const R = 250;
  return (
    <div className="relative mx-auto" style={{ width: 600, height: 600 }}>
      <svg viewBox="0 0 600 600" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id="fwflow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#B6FF3C"/><stop offset=".5" stopColor="#4CD4F0"/><stop offset="1" stopColor="#A78BFA"/>
          </linearGradient>
          <radialGradient id="fwsweep"><stop offset="0" stopColor="rgba(182,255,60,0)"/><stop offset="1" stopColor="rgba(182,255,60,.5)"/></radialGradient>
        </defs>
        <circle cx="300" cy="300" r={R} fill="none" stroke="var(--line,#232B3C)" strokeWidth="1.5"/>
        {!paused && (
          <circle cx="300" cy="300" r={R} fill="none" stroke="url(#fwflow)" strokeWidth="2.5"
            strokeLinecap="round" strokeDasharray="6 16" className="fw-flow"/>
        )}
        {!paused && (
          <g className="fw-sweep"><path d="M300 300 L300 50 A250 250 0 0 1 476 124 Z" fill="url(#fwsweep)" opacity=".18"/></g>
        )}
      </svg>

      {/* core */}
      <div className="absolute left-1/2 top-1/2 flex flex-col items-center justify-center gap-[2px] text-center"
        style={{ transform: "translate(-50%,-50%)", width: 230, height: 230, borderRadius: "50%",
          border: "1px solid var(--line,#232B3C)",
          background: "radial-gradient(circle at 50% 40%, rgba(182,255,60,.10), rgba(17,21,31,.9) 68%)" }}>
        <div className="font-display text-[44px] font-black leading-none tracking-tight text-lime tabnums">
          {deliveredToday}<span className="text-[14px] font-semibold text-muted"> 条/日</span></div>
        <div className="font-mono text-[11px] text-muted">今日已交付</div>
        <div className="mt-[6px] font-mono text-[12px] text-text">在跑 <b className="text-cyan">{autopilotCount}</b> 个自动驾驶账号</div>
        <div className={`mt-2 font-mono text-[10px] uppercase tracking-[.22em] ${paused ? "text-warn" : "text-good"}`}>
          {paused ? "● PAUSED" : "● SELF-SPINNING"}</div>
      </div>

      {/* nodes */}
      {steps.slice(0, 9).map((s, i) => {
        const angle = -90 + i * 40;
        const on = s.status === "ok";
        return (
          <div key={s.key} className="absolute left-1/2 top-1/2 text-center"
            style={{ width: 118, marginLeft: -59, marginTop: -34,
              transform: `rotate(${angle}deg) translateY(-${R}px) rotate(${-angle}deg)`, ["--nc" as string]: NC[s.key] }}>
            <div className={`relative mx-auto flex items-center justify-center rounded-[17px] border transition-colors ${on ? "fw-node-on" : ""}`}
              style={{ width: 58, height: 58, color: NC[s.key],
                background: on ? "color-mix(in oklab, var(--nc) 13%, transparent)" : "var(--panel2,#151A26)",
                borderColor: on ? NC[s.key] : "var(--line,#232B3C)",
                boxShadow: on ? "0 0 22px color-mix(in oklab, var(--nc) 28%, transparent)" : "none" }}>
              <svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor"
                strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{ICON[s.key]}</svg>
              <span className="absolute -left-[7px] -top-[7px] flex h-[19px] w-[19px] items-center justify-center rounded-full border border-line bg-bg font-mono text-[10px] text-muted">{i + 1}</span>
            </div>
            <div className="mt-[7px] font-sans text-[12px] font-bold text-text">{s.label}</div>
            <div className="mt-[1px] font-mono text-[10.5px]" style={{ color: on ? NC[s.key] : "var(--muted,#8A97AC)" }}>{s.count}</div>
          </div>
        );
      })}
    </div>
  );
}
```

Note: if the Tailwind theme tokens aren't exposed as CSS custom properties (`--lime` etc.), the `var(--lime,#B6FF3C)` fallbacks still render correct colors — verify the hexes match the tokens (they do: lime #B6FF3C, cyan #4CD4F0, violet #A78BFA, pink #FF6FB5, line #232B3C, panel2 #151A26). `tabnums` is an existing utility in this app (used in Flow.tsx); if not defined, use `tabular-nums` via `style={{ fontVariantNumeric: "tabular-nums" }}`.

- [ ] **Step 2: Commit** `git add frontend/src/components/FlywheelChart.tsx` + commit `feat(fe): FlywheelChart animated ring component`.

---

### Task 4: `Flywheel` page

**Files:** Create `frontend/src/pages/Flywheel.tsx`; Test in Task 6.

- [ ] **Step 1: Implement** `frontend/src/pages/Flywheel.tsx` — compose chart + KPI strip + autopilot rail + activity feed + pause control, driven by `useAsync(() => api.getFlywheel())`.

```tsx
import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { FlywheelState } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";
import { FlywheelChart } from "../components/FlywheelChart";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok", twitter: "X",
  weixin_video: "视频号", weixin_gzh: "公众号", youtube: "YouTube", instagram: "IG", bilibili: "B站",
};
const EMPTY: FlywheelState = { paused: false, autopilot_accounts: 0, pending_review: 0, steps: [], accounts: [], events: [] };

export function Flywheel() {
  const fw = useAsync(() => api.getFlywheel(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const d: FlywheelState = fw.data ?? EMPTY;

  const delivered = useMemo(
    () => (d.steps.find((s) => s.key === "publish")?.count ?? 0), [d.steps]);

  async function toggleAutopilot(id: number, enabled: boolean) {
    setBusy(`ap-${id}`);
    try { await api.setAutopilot(id, enabled); fw.reload(); } finally { setBusy(null); }
  }
  async function togglePause() {
    setBusy("pause");
    try { d.paused ? await api.resumeFlywheel() : await api.pauseFlywheel(); fw.reload(); } finally { setBusy(null); }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">内容自转<span className="text-lime">飞轮</span></h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">爬爆款 → 定调 → 脚本 → 视频 → 发布 → 追踪 → 复盘 → 评估 → 改进 · <span className="text-warn">下班无人值守</span></p>
        </div>
        <div className="flex-1" />
        <button onClick={togglePause} disabled={busy === "pause"} aria-label="暂停或恢复飞轮"
          className={`rounded-lg border px-4 py-2 font-mono text-xs transition-colors disabled:opacity-50 ${d.paused ? "border-good/50 bg-good/[.1] text-good" : "border-alert/50 bg-alert/[.08] text-alert"}`}>
          {d.paused ? "▶ 恢复飞轮" : "⏸ 暂停飞轮"}
        </button>
      </div>

      {fw.error && <div className="px-1 pb-3 font-mono text-alert">加载失败：{fw.error}</div>}

      <div className="mb-[14px] grid grid-cols-2 gap-[14px] md:grid-cols-4">
        <StatTile label="今日交付(发布)" value={String(delivered)} accent />
        <StatTile label="自动驾驶账号" value={`${d.autopilot_accounts} / ${d.accounts.length}`} />
        <StatTile label="待人工审核" value={String(d.pending_review)} />
        <StatTile label="飞轮状态" value={d.paused ? "已暂停" : "自转中"} />
      </div>

      <div className="grid gap-[14px] lg:grid-cols-[1.55fr_.95fr]">
        <ChartCard title="🌀 内容自转飞轮" pill="9 步 · 实时" glow className="rise min-h-[660px]">
          <FlywheelChart steps={d.steps} deliveredToday={delivered} autopilotCount={d.autopilot_accounts} paused={d.paused} />
        </ChartCard>

        <div className="flex flex-col gap-[14px]">
          <ChartCard title="🛩 自动驾驶账号" pill={`${d.autopilot_accounts} 开`}>
            <div className="space-y-[2px]">
              {d.accounts.map((a) => (
                <div key={a.id} className="flex items-center gap-3 border-t border-line py-[10px] first:border-t-0">
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-[13px] font-bold text-text">{a.handle}</div>
                    <div className="font-mono text-[10.5px] text-muted">{PLATFORM_LABEL[a.platform] ?? a.platform}</div>
                  </div>
                  <button onClick={() => toggleAutopilot(a.id, !a.autopilot)} disabled={busy === `ap-${a.id}`}
                    aria-label={`切换 ${a.handle} 自动驾驶`}
                    className={`relative h-6 w-11 rounded-full border transition-colors disabled:opacity-50 ${a.autopilot ? "border-lime bg-lime/[.18]" : "border-line bg-panel2"}`}>
                    <span className={`absolute top-[2px] h-[18px] w-[18px] rounded-full transition-all ${a.autopilot ? "left-[22px] bg-lime" : "left-[2px] bg-muted"}`} />
                  </button>
                </div>
              ))}
              {d.accounts.length === 0 && <p className="py-6 text-center font-mono text-[11px] text-muted">还没有账号。</p>}
            </div>
          </ChartCard>

          <ChartCard title="⚡ 飞轮流水" pill="实时">
            <div className="space-y-[2px]">
              {d.events.map((e, i) => (
                <div key={i} className="flex items-baseline gap-[10px] border-t border-line py-[9px] font-mono text-[11.5px] first:border-t-0">
                  <span className="text-dim">{e.ts ? e.ts.slice(11, 16) : "--:--"}</span>
                  <span className={e.status === "ok" ? "text-cyan" : e.status === "blocked" ? "text-warn" : e.status === "error" ? "text-alert" : "text-muted"}>{e.step}</span>
                  <span className="min-w-0 flex-1 truncate text-muted">{e.detail}</span>
                </div>
              ))}
              {d.events.length === 0 && <p className="py-6 text-center font-mono text-[11px] text-muted">飞轮还没转过 —— 打开账号自动驾驶或跑一批后这里出流水。</p>}
            </div>
          </ChartCard>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit** `git add frontend/src/pages/Flywheel.tsx` + commit `feat(fe): Flywheel command-center page`.

---

### Task 5: Route + nav (flywheel as home)

- [ ] **Step 1:** In `frontend/src/App.tsx`: import `Flywheel`; change `<Route path="/" element={<Overview />} />` to `<Route path="/" element={<Flywheel />} />` and add `<Route path="/overview" element={<Overview />} />`.

- [ ] **Step 2:** In `frontend/src/components/Layout.tsx`: update `NAV` to lead with 飞轮 and add 视频:

```ts
const NAV = [
  { to: "/", label: "飞轮" },
  { to: "/overview", label: "总览" },
  { to: "/video", label: "视频" },
  { to: "/flow", label: "导流" },
  { to: "/content", label: "爆文库" },
  { to: "/compare", label: "对比" },
];
```

The active-check for `/` already uses exact match (`n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)`) — keep it; ensure `/overview` startsWith logic doesn't also match `/` (it won't, since `/` uses exact).

- [ ] **Step 3: Typecheck** `npx tsc --noEmit` → exit 0.

- [ ] **Step 4: Commit** `git add frontend/src/App.tsx frontend/src/components/Layout.tsx` + commit `feat(fe): flywheel as home + nav lead`.

---

### Task 6: Tests

**Files:** Create `frontend/src/pages/Flywheel.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Flywheel } from "./Flywheel";

const STATE = {
  paused: false, autopilot_accounts: 1, pending_review: 2,
  steps: [
    { key: "crawl", label: "爬爆款", count: 0, status: "pending" },
    { key: "brief", label: "定调", count: 6, status: "ok" },
    { key: "script", label: "脚本", count: 3, status: "ok" },
    { key: "video", label: "视频", count: 1, status: "ok" },
    { key: "publish", label: "发布", count: 4, status: "ok" },
    { key: "track", label: "追踪流量", count: 5, status: "ok" },
    { key: "retro", label: "复盘", count: 2, status: "ok" },
    { key: "evaluate", label: "账号评估", count: 6, status: "ok" },
    { key: "improve", label: "改进建议", count: 3, status: "ok" },
  ],
  accounts: [{ id: 4, handle: "@money_talk", platform: "twitter", autopilot: false }],
  events: [{ account_id: 4, step: "script", status: "ok", detail: "生成《Fed》", ts: "2026-07-09T21:02:00+00:00" }],
};

function stub(routes: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const c = routes(String(url), init);
    return Promise.resolve(c !== undefined ? c : { ok: true, json: async () => ({}) });
  }));
}
beforeEach(() => { stub((url) => (url.endsWith("/flywheel") ? { ok: true, json: async () => STATE } : undefined)); });
afterEach(() => vi.unstubAllGlobals());

it("renders the 9 flywheel steps + delivered count from /flywheel", async () => {
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  expect(await screen.findByText("发布")).toBeInTheDocument();
  expect(screen.getByText("追踪流量")).toBeInTheDocument();
  // delivered = publish count = 4 shown in core
  await waitFor(() => expect(screen.getAllByText("4").length).toBeGreaterThan(0));
});

it("toggling an account calls POST /accounts/{id}/autopilot", async () => {
  const calls: string[] = [];
  stub((url, init) => {
    if (url.endsWith("/flywheel")) return { ok: true, json: async () => STATE };
    if (url.match(/\/accounts\/4\/autopilot$/) && init?.method === "POST") { calls.push(String(init?.body)); return { ok: true, json: async () => ({ account_id: 4, autopilot: true }) }; }
    return undefined;
  });
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /切换 @money_talk 自动驾驶/ }));
  await waitFor(() => expect(calls.length).toBe(1));
  expect(calls[0]).toContain("true");
});

it("pause button calls POST /flywheel/pause", async () => {
  const calls: string[] = [];
  stub((url, init) => {
    if (url.endsWith("/flywheel")) return { ok: true, json: async () => STATE };
    if (url.endsWith("/flywheel/pause") && init?.method === "POST") { calls.push("pause"); return { ok: true, json: async () => ({ paused: true }) }; }
    return undefined;
  });
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /暂停或恢复飞轮/ }));
  await waitFor(() => expect(calls).toContain("pause"));
});
```

- [ ] **Step 2: Run** `npx vitest run src/pages/Flywheel.test.tsx` → PASS (3 tests). Fix component if a real issue surfaces.

- [ ] **Step 3: Full suite + typecheck** `npx tsc --noEmit && npx vitest run` → clean; all pass (38 + 3 = 41).

- [ ] **Step 4: Commit** `git add frontend/src/pages/Flywheel.test.tsx` + commit `test(fe): flywheel page (steps render, autopilot toggle, pause)`.

---

## After all tasks

- Final code review (react-reviewer) over the branch diff.
- `superpowers:finishing-a-development-branch` → merge to `main` (`--no-ff`).
- Restart frontend; open `http://127.0.0.1:5173/` — the flywheel is home, spinning, driven by live `/flywheel`; toggle an account's autopilot; pause/resume.

## Self-review

- **Coverage:** api+types (T1), keyframes (T2), FlywheelChart animated ring driven by `/flywheel` steps (T3), Flywheel page with KPI + autopilot rail + feed + pause control (T4), flywheel-as-home + nav (T5), tests (T6). Matches the approved mockup; reduced-motion respected.
- **Type consistency:** `FlywheelState`/`FlywheelStep` etc. match the backend `GET /flywheel` shape (steps[key,label,count,status], accounts[id,handle,platform,autopilot], events, paused, autopilot_accounts, pending_review); client method signatures match call sites.
- **No placeholders:** full component + page code, exact commands.
