# MatrixLoop Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个「深色指挥台」美学的 Dashboard 前端，消费 plan 5 的 FastAPI，落地两页：总览（矩阵健康 stat tiles + 需处理队列 + 可排序账号表）与单账号下钻（价值分 + KPI + ECharts 趋势/评估雷达 + Loop 历史时间线 + 待审产出面板）。

**Architecture:** Vite + React 18 + TypeScript + Tailwind + ECharts（经 `echarts-for-react`）。`react-router-dom` 两路由：`/`（Overview）、`/accounts/:id`（Detail）。类型化 `fetch` 客户端命中后端（base URL 走 `VITE_API_BASE`，默认 `http://localhost:8000`）。设计令牌集中在 Tailwind theme + `index.css` CSS 变量，锁定「深色指挥台 + 青柠强调」美学。测试用 vitest + React Testing Library（组件渲染 smoke + API URL 构造），`npm run build`（tsc + vite build）作为编译门槛。视觉最终由浏览器截图人工核验。

**Tech Stack:** Node v26 / npm。react, react-dom, react-router-dom, echarts, echarts-for-react, tailwindcss v3, vite, typescript, vitest, @testing-library/react, jsdom。

**位置：** 全部在 `frontend/`（仓库已存在空目录）。后端在 `backend/`，本计划不改后端。

**美学锁定（frontend-design 已定）：**
- 深色底 `--bg:#0B0E14`，面板 `--panel:#12161F`，描边 `--line:#232A38`，正文 `--text:#E6E9EF`，弱化 `--muted:#8B93A7`
- 强调色 青柠 `--accent:#B6FF3C`；状态 绿 `#3ECf8e`(worked/健康) / 琥珀 `#F5A524`(no_progress/待审) / 红 `#F0526B`(连跌告警)
- 字体：标题 `Archivo`，数字/标签 `IBM Plex Mono`，正文/中文 `Noto Sans SC`（均 Google Fonts）
- 细节：极细描边分层、微噪点背景、等宽表格数字、状态点带微光、载入错峰淡入

---

### Task 1: 脚手架 + 设计系统 + 应用外壳

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/.env`
- Create: `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`

- [ ] **Step 1: 初始化项目与依赖**

Run:
```bash
cd /Users/aa00102/matrix-loop/frontend
npm init -y >/dev/null
npm install react@18 react-dom@18 react-router-dom@6 echarts echarts-for-react
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss@3 postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom jsdom
node -e "console.log('deps ok')"
```
Expected: 安装完成，打印 `deps ok`

- [ ] **Step 2: 写配置文件**

Create `frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"] },
});
```

Create `frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": { "composite": true, "skipLibCheck": true, "module": "ESNext", "moduleResolution": "bundler", "allowSyntheticDefaultImports": true },
  "include": ["vite.config.ts"]
}
```

Create `frontend/postcss.config.js`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

Create `frontend/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E14",
        panel: "#12161F",
        line: "#232A38",
        text: "#E6E9EF",
        muted: "#8B93A7",
        accent: "#B6FF3C",
        good: "#3ECF8E",
        warn: "#F5A524",
        alert: "#F0526B",
      },
      fontFamily: {
        display: ["Archivo", "Noto Sans SC", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
        sans: ["'Noto Sans SC'", "Archivo", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

Create `frontend/.env`:
```
VITE_API_BASE=http://localhost:8000
```

Create `frontend/index.html`:
```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MatrixLoop</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=IBM+Plex+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: 写设计系统 CSS 与入口**

Create `frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { color-scheme: dark; }

body {
  margin: 0;
  background-color: #0B0E14;
  /* 微噪点 + 极淡径向光，营造深度而非纯色平板 */
  background-image:
    radial-gradient(1200px 600px at 80% -10%, rgba(182,255,60,0.05), transparent 60%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.02'/%3E%3C/svg%3E");
  color: #E6E9EF;
  font-family: "Noto Sans SC", Archivo, sans-serif;
}

.tabnums { font-variant-numeric: tabular-nums; }

@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.rise { animation: rise 0.4s ease both; }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #232A38; border-radius: 6px; }
::-webkit-scrollbar-track { background: transparent; }
```

Create `frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

Create `frontend/src/components/Layout.tsx`:
```tsx
import { Link } from "react-router-dom";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line px-6 py-3 flex items-center gap-6">
        <Link to="/" className="font-display font-extrabold tracking-tight text-lg">
          Matrix<span className="text-accent">Loop</span>
        </Link>
        <span className="font-mono text-xs text-muted">矩阵账号 · 自我修正指挥台</span>
      </header>
      <main className="px-6 py-6 max-w-[1400px] mx-auto">{children}</main>
    </div>
  );
}
```

Create `frontend/src/App.tsx`:
```tsx
import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { AccountDetail } from "./pages/AccountDetail";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/accounts/:id" element={<AccountDetail />} />
      </Routes>
    </Layout>
  );
}
```

Create `frontend/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 4: 加脚本并验证 typecheck**

Edit `frontend/package.json` — set the `"scripts"` block to:
```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
```
Also add `"type": "module"` to package.json if not present.

Note: `App.tsx` imports `./pages/Overview` and `./pages/AccountDetail`, created in Tasks 3-4. To let Task 1 typecheck standalone, create temporary stubs now:

Create `frontend/src/pages/Overview.tsx`:
```tsx
export function Overview() { return <div className="font-mono text-muted">Overview…</div>; }
```
Create `frontend/src/pages/AccountDetail.tsx`:
```tsx
export function AccountDetail() { return <div className="font-mono text-muted">Detail…</div>; }
```

- [ ] **Step 5: 验证 build 通过**

Run: `cd /Users/aa00102/matrix-loop/frontend && npm run build 2>&1 | tail -5`
Expected: vite build 成功产出 `dist/`（无 tsc 报错）

- [ ] **Step 6: 提交**

```bash
cd /Users/aa00102/matrix-loop
printf '\nnode_modules/\nfrontend/dist/\n' >> .gitignore
git add frontend .gitignore
git commit -m "feat(dashboard): scaffold Vite+React+TS+Tailwind, dark command-center design system + app shell"
```

---

### Task 2: 类型化 API 客户端 + hooks

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`
- Test: `frontend/src/api/client.test.ts`

- [ ] **Step 1: 写失败的 client 测试**

Create `frontend/src/api/client.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./client";

describe("api client", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("GET /accounts hits the base url", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    await api.listAccounts();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/accounts", expect.any(Object));
  });

  it("POST setRecommendationStatus sends body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1, kind: "positioning", content: "x", status: "adopted" }) });
    vi.stubGlobal("fetch", fetchMock);
    const out = await api.setRecommendationStatus(1, "adopted");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/recommendations/1/status",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ status: "adopted" }) }),
    );
    expect(out.status).toBe("adopted");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: "nope" }) }));
    await expect(api.getAccount(999)).rejects.toThrow();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/aa00102/matrix-loop/frontend && npx vitest run src/api/client.test.ts 2>&1 | tail -8`
Expected: FAIL - `Cannot find module './client'`

- [ ] **Step 3: 实现 types / client / hooks**

Create `frontend/src/api/types.ts`:
```ts
export interface AccountListItem {
  id: number;
  platform: string;
  handle: string;
  vertical: string | null;
  positioning: string | null;
  latest_followers: number | null;
  latest_composite_score: number | null;
  latest_loop_status: string | null;
  source_tier: string | null;
}

export interface SnapshotOut {
  id: number; ts: string; followers: number | null; engagement_rate: number | null;
  hit_rate: number | null; conversions: number | null; source_tier: string;
}
export interface ContentItemOut { id: number; topic: string | null; views: number | null; likes: number | null; }
export interface RecommendationOut { id: number; kind: string; content: string; status: string; }
export interface DraftOut { id: number; kind: string; content: string; review_status: string; }
export interface EvaluationOut { id: number; composite_score: number; breakdown: Record<string, number>; created_at: string; }
export interface LoopRunOut {
  id: number; ts: string; diagnosis: string | null; verify_result: Record<string, unknown>; status: string;
  evaluation: EvaluationOut | null; recommendations: RecommendationOut[]; drafts: DraftOut[];
}
export interface AccountDetail {
  id: number; platform: string; handle: string; vertical: string | null; positioning: string | null;
  objective_weights: Record<string, number> | null;
  snapshots: SnapshotOut[]; content_items: ContentItemOut[]; loop_runs: LoopRunOut[];
}
```

Create `frontend/src/api/client.ts`:
```ts
import type { AccountListItem, AccountDetail, LoopRunOut, RecommendationOut, DraftOut } from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string) ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.status.toString();
    try { detail = (await res.json())?.detail ?? detail; } catch { /* ignore */ }
    throw new Error(`API ${path} failed: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listAccounts: () => req<AccountListItem[]>("/accounts"),
  getAccount: (id: number) => req<AccountDetail>(`/accounts/${id}`),
  triggerLoop: (id: number) => req<LoopRunOut>(`/accounts/${id}/loop`, { method: "POST" }),
  setRecommendationStatus: (id: number, status: string) =>
    req<RecommendationOut>(`/recommendations/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  setDraftStatus: (id: number, review_status: string) =>
    req<DraftOut>(`/drafts/${id}/status`, { method: "POST", body: JSON.stringify({ review_status }) }),
};
```

Create `frontend/src/api/hooks.ts`:
```ts
import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const run = useCallback(() => {
    setLoading(true);
    fn().then(setData).catch((e) => setError(String(e))).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd /Users/aa00102/matrix-loop/frontend && npx vitest run src/api/client.test.ts 2>&1 | tail -8`
Expected: PASS (3 passed)

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/api
git commit -m "feat(dashboard): typed API client + types + useAsync hook"
```

---

### Task 3: 总览页（stat tiles + 待办队列 + 账号表）

**Files:**
- Create: `frontend/src/components/StatTile.tsx`, `frontend/src/components/StatusDot.tsx`, `frontend/src/components/ScoreBar.tsx`
- Rewrite: `frontend/src/pages/Overview.tsx`
- Test: `frontend/src/pages/Overview.test.tsx`

设计要点：顶部一行 stat tiles（总账号 / 平均价值分 / 需介入数 / 平台数），青柠强调关键数字；「今天需要处理」队列只列 `latest_loop_status==='no_progress'` 的账号（v1；待审草稿/建议在下钻页处理，TODO: 后续加 /queue 端点做精确计数）；下方账号表可点表头排序（价值分/涨粉），行内状态点 + 价值分条，点行进下钻。

- [ ] **Step 1: 写失败的总览测试**

Create `frontend/src/pages/Overview.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Overview } from "./Overview";
import type { AccountListItem } from "../api/types";

const ACCOUNTS: AccountListItem[] = [
  { id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: null, latest_followers: 88000, latest_composite_score: 88, latest_loop_status: "ok", source_tier: "manual" },
  { id: 2, platform: "tiktok", handle: "@a2", vertical: null, positioning: null, latest_followers: 45000, latest_composite_score: 63, latest_loop_status: "no_progress", source_tier: "scrape" },
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ACCOUNTS }));
});

it("renders stat tiles and both accounts in the table", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  expect(await screen.findByText("@a1")).toBeInTheDocument();
  expect(screen.getByText("@a2")).toBeInTheDocument();
  // 需介入队列出现 no_progress 的 @a2
  expect(screen.getByText(/需介入|no_progress/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/aa00102/matrix-loop/frontend && npx vitest run src/pages/Overview.test.tsx 2>&1 | tail -8`
Expected: FAIL（Overview 还是 stub，找不到 @a1）

- [ ] **Step 3: 实现小组件 + 总览页**

Create `frontend/src/components/StatusDot.tsx`:
```tsx
const MAP: Record<string, { color: string; label: string }> = {
  ok: { color: "#3ECF8E", label: "正常" },
  no_progress: { color: "#F5A524", label: "需介入" },
  error: { color: "#F0526B", label: "错误" },
  budget_stop: { color: "#F0526B", label: "超预算" },
};
export function StatusDot({ status }: { status: string | null }) {
  const s = (status && MAP[status]) || { color: "#8B93A7", label: status ?? "未跑" };
  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs">
      <span className="h-2 w-2 rounded-full" style={{ background: s.color, boxShadow: `0 0 8px ${s.color}` }} />
      {s.label}
    </span>
  );
}
```

Create `frontend/src/components/ScoreBar.tsx`:
```tsx
export function ScoreBar({ score }: { score: number | null }) {
  if (score == null) return <span className="font-mono text-muted text-xs">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded bg-line overflow-hidden">
        <div className="h-full rounded bg-accent" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
      <span className="font-mono text-sm tabnums">{score.toFixed(0)}</span>
    </div>
  );
}
```

Create `frontend/src/components/StatTile.tsx`:
```tsx
export function StatTile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3 rise">
      <div className="font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`font-display text-2xl mt-1 tabnums ${accent ? "text-accent" : "text-text"}`}>{value}</div>
    </div>
  );
}
```

Rewrite `frontend/src/pages/Overview.tsx`:
```tsx
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { AccountListItem } from "../api/types";
import { StatTile } from "../components/StatTile";
import { StatusDot } from "../components/StatusDot";
import { ScoreBar } from "../components/ScoreBar";

type SortKey = "score" | "followers";

export function Overview() {
  const { data, loading, error } = useAsync(() => api.listAccounts(), []);
  const [sort, setSort] = useState<SortKey>("score");

  const accounts = useMemo(() => data ?? [], [data]);
  const needsAttention = accounts.filter((a) => a.latest_loop_status === "no_progress");
  const avgScore = accounts.length
    ? accounts.reduce((s, a) => s + (a.latest_composite_score ?? 0), 0) / accounts.length
    : 0;
  const platforms = new Set(accounts.map((a) => a.platform)).size;

  const sorted = [...accounts].sort((a, b) =>
    sort === "score"
      ? (b.latest_composite_score ?? -1) - (a.latest_composite_score ?? -1)
      : (b.latest_followers ?? -1) - (a.latest_followers ?? -1),
  );

  if (loading) return <div className="font-mono text-muted">加载中…</div>;
  if (error) return <div className="font-mono text-alert">加载失败：{error}</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="账号总数" value={String(accounts.length)} />
        <StatTile label="平均价值分" value={avgScore.toFixed(0)} accent />
        <StatTile label="需介入" value={String(needsAttention.length)} />
        <StatTile label="覆盖平台" value={String(platforms)} />
      </div>

      <section className="rounded-lg border border-line bg-panel p-4 rise">
        <h2 className="font-display text-sm mb-3">⚠️ 今天需要处理</h2>
        {needsAttention.length === 0 ? (
          <p className="font-mono text-xs text-muted">暂无需介入账号。</p>
        ) : (
          <ul className="space-y-2">
            {needsAttention.map((a) => (
              <li key={a.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
                <span className="font-mono text-sm">{a.handle} · {a.platform} · <span className="text-warn">需介入 (连续无进展)</span></span>
                <Link to={`/accounts/${a.id}`} className="font-mono text-xs text-accent hover:underline">查看 →</Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-line bg-panel overflow-hidden rise">
        <div className="flex items-center gap-4 px-4 py-2 border-b border-line font-mono text-xs text-muted">
          <span>全部账号</span>
          <button onClick={() => setSort("score")} className={sort === "score" ? "text-accent" : ""}>按价值分</button>
          <button onClick={() => setSort("followers")} className={sort === "followers" ? "text-accent" : ""}>按粉丝</button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="font-mono text-[11px] uppercase text-muted">
              <th className="text-left px-4 py-2">账号</th>
              <th className="text-left px-4 py-2">平台</th>
              <th className="text-left px-4 py-2">价值分</th>
              <th className="text-right px-4 py-2">粉丝</th>
              <th className="text-left px-4 py-2">Loop</th>
              <th className="text-left px-4 py-2">数据档位</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((a: AccountListItem) => (
              <tr key={a.id} className="border-t border-line hover:bg-line/30">
                <td className="px-4 py-2">
                  <Link to={`/accounts/${a.id}`} className="hover:text-accent">{a.handle}</Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-muted">{a.platform}</td>
                <td className="px-4 py-2"><ScoreBar score={a.latest_composite_score} /></td>
                <td className="px-4 py-2 text-right font-mono tabnums">{a.latest_followers?.toLocaleString() ?? "—"}</td>
                <td className="px-4 py-2"><StatusDot status={a.latest_loop_status} /></td>
                <td className="px-4 py-2 font-mono text-xs text-muted">{a.source_tier ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: 运行确认通过 + build**

Run: `cd /Users/aa00102/matrix-loop/frontend && npx vitest run src/pages/Overview.test.tsx 2>&1 | tail -6 && npm run build 2>&1 | tail -3`
Expected: 测试 PASS 且 build 成功

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src
git commit -m "feat(dashboard): Overview page - stat tiles, attention queue, sortable account table"
```

---

### Task 4: 单账号下钻页（分数/KPI/ECharts/时间线/审核）

**Files:**
- Create: `frontend/src/components/TrendChart.tsx`, `frontend/src/components/ScoreRadar.tsx`, `frontend/src/components/LoopTimeline.tsx`, `frontend/src/components/ReviewPanel.tsx`
- Rewrite: `frontend/src/pages/AccountDetail.tsx`
- Test: `frontend/src/pages/AccountDetail.test.tsx`

设计要点：顶部大号价值分（青柠）+ 平台/handle；KPI 行（粉丝/互动/爆文率/转化 来自最新快照）；ECharts 折线（粉丝随快照时间）+ 雷达（最新 loop 的 evaluation.breakdown 四维）；Loop 历史时间线（每轮 diagnosis + verify delta + 状态点）；待审产出面板（最新 loop 的 recommendations/drafts + 采纳/否决按钮 → 调 API → reload）；「跑一轮 Loop」按钮 → triggerLoop → reload。ECharts 主题用暗底 + 青柠。为测试稳定，`ScoreRadar`/`TrendChart` 用 `echarts-for-react`，测试里 mock 掉。

- [ ] **Step 1: 写失败的下钻测试（mock echarts-for-react）**

Create `frontend/src/pages/AccountDetail.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AccountDetail } from "./AccountDetail";
import type { AccountDetail as AccountDetailT } from "../api/types";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const DETAIL: AccountDetailT = {
  id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: "美妆",
  objective_weights: { growth: 1, engagement: 0, commercial: 0, positioning: 0 },
  snapshots: [
    { id: 1, ts: "2026-07-01T00:00:00+00:00", followers: 100000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 2, source_tier: "manual" },
    { id: 2, ts: "2026-07-06T00:00:00+00:00", followers: 110000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 3, source_tier: "manual" },
  ],
  content_items: [],
  loop_runs: [
    { id: 9, ts: "2026-07-06T01:00:00+00:00", diagnosis: "定位偏散，建议聚焦", verify_result: { improved: true, delta: 12 }, status: "ok",
      evaluation: { id: 3, composite_score: 88, breakdown: { growth: 90, engagement: 85, commercial: 80, positioning: 95 }, created_at: "2026-07-06T01:00:00+00:00" },
      recommendations: [{ id: 5, kind: "positioning", content: "聚焦平价美妆测评", status: "pending" }],
      drafts: [{ id: 7, kind: "topic", content: "5款百元粉底横评", review_status: "pending" }] },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => DETAIL }));
});

it("renders score, diagnosis, and review items", async () => {
  render(
    <MemoryRouter initialEntries={["/accounts/1"]}>
      <Routes><Route path="/accounts/:id" element={<AccountDetail />} /></Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("@a1")).toBeInTheDocument();
  expect(screen.getByText("88")).toBeInTheDocument();               // 价值分
  expect(screen.getByText(/定位偏散/)).toBeInTheDocument();          // 诊断
  expect(screen.getByText(/聚焦平价美妆测评/)).toBeInTheDocument();   // 建议
  expect(screen.getByText(/5款百元粉底横评/)).toBeInTheDocument();    // 草稿
  expect(screen.getAllByTestId("echart").length).toBeGreaterThanOrEqual(1);
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/aa00102/matrix-loop/frontend && npx vitest run src/pages/AccountDetail.test.tsx 2>&1 | tail -8`
Expected: FAIL（AccountDetail 仍是 stub）

- [ ] **Step 3: 实现图表/时间线/审核组件 + 下钻页**

Create `frontend/src/components/TrendChart.tsx`:
```tsx
import ReactECharts from "echarts-for-react";
import type { SnapshotOut } from "../api/types";

export function TrendChart({ snapshots }: { snapshots: SnapshotOut[] }) {
  const ordered = [...snapshots].sort((a, b) => a.ts.localeCompare(b.ts));
  const option = {
    backgroundColor: "transparent",
    grid: { top: 24, right: 16, bottom: 24, left: 48 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: ordered.map((s) => s.ts.slice(5, 10)), axisLine: { lineStyle: { color: "#232A38" } }, axisLabel: { color: "#8B93A7", fontFamily: "IBM Plex Mono" } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#232A38" } }, axisLabel: { color: "#8B93A7", fontFamily: "IBM Plex Mono" } },
    series: [{ type: "line", smooth: true, data: ordered.map((s) => s.followers ?? 0), lineStyle: { color: "#B6FF3C", width: 2 }, itemStyle: { color: "#B6FF3C" }, areaStyle: { color: "rgba(182,255,60,0.08)" } }],
  };
  return <ReactECharts option={option} style={{ height: 200 }} />;
}
```

Create `frontend/src/components/ScoreRadar.tsx`:
```tsx
import ReactECharts from "echarts-for-react";

const DIMS: { key: string; name: string }[] = [
  { key: "growth", name: "涨粉" }, { key: "engagement", name: "互动" },
  { key: "commercial", name: "商业" }, { key: "positioning", name: "定位" },
];

export function ScoreRadar({ breakdown }: { breakdown: Record<string, number> }) {
  const option = {
    backgroundColor: "transparent",
    radar: {
      indicator: DIMS.map((d) => ({ name: d.name, max: 100 })),
      axisName: { color: "#8B93A7", fontFamily: "IBM Plex Mono" },
      splitLine: { lineStyle: { color: "#232A38" } }, splitArea: { show: false }, axisLine: { lineStyle: { color: "#232A38" } },
    },
    series: [{ type: "radar", data: [{ value: DIMS.map((d) => breakdown[d.key] ?? 0), lineStyle: { color: "#B6FF3C" }, areaStyle: { color: "rgba(182,255,60,0.15)" }, itemStyle: { color: "#B6FF3C" } }] }],
  };
  return <ReactECharts option={option} style={{ height: 200 }} />;
}
```

Create `frontend/src/components/LoopTimeline.tsx`:
```tsx
import type { LoopRunOut } from "../api/types";
import { StatusDot } from "./StatusDot";

export function LoopTimeline({ runs }: { runs: LoopRunOut[] }) {
  const ordered = [...runs].sort((a, b) => b.ts.localeCompare(a.ts));
  return (
    <ul className="space-y-3">
      {ordered.map((r) => {
        const delta = (r.verify_result?.delta as number | undefined) ?? null;
        return (
          <li key={r.id} className="border-l-2 border-line pl-3">
            <div className="flex items-center gap-3 font-mono text-xs text-muted">
              <span>{r.ts.slice(0, 16).replace("T", " ")}</span>
              <StatusDot status={r.status} />
              {delta != null && <span className={delta > 0 ? "text-good" : "text-muted"}>Δ {delta > 0 ? "+" : ""}{delta}</span>}
            </div>
            {r.diagnosis && <p className="text-sm mt-1">{r.diagnosis}</p>}
          </li>
        );
      })}
    </ul>
  );
}
```

Create `frontend/src/components/ReviewPanel.tsx`:
```tsx
import { api } from "../api/client";
import type { LoopRunOut } from "../api/types";

export function ReviewPanel({ run, onChange }: { run: LoopRunOut; onChange: () => void }) {
  const act = async (fn: () => Promise<unknown>) => { await fn(); onChange(); };
  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-mono text-xs text-muted uppercase mb-2">纠偏建议</h3>
        <ul className="space-y-2">
          {run.recommendations.map((rec) => (
            <li key={rec.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
              <span className="text-sm"><span className="font-mono text-xs text-muted">[{rec.kind}]</span> {rec.content}</span>
              <span className="flex items-center gap-2 font-mono text-xs">
                {rec.status === "pending" ? (
                  <>
                    <button className="text-good hover:underline" onClick={() => act(() => api.setRecommendationStatus(rec.id, "adopted"))}>采纳</button>
                    <button className="text-alert hover:underline" onClick={() => act(() => api.setRecommendationStatus(rec.id, "rejected"))}>否决</button>
                  </>
                ) : <span className="text-muted">{rec.status}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="font-mono text-xs text-muted uppercase mb-2">起草选题 / 脚本（待审）</h3>
        <ul className="space-y-2">
          {run.drafts.map((d) => (
            <li key={d.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
              <span className="text-sm"><span className="font-mono text-xs text-muted">[{d.kind}]</span> {d.content}</span>
              <span className="flex items-center gap-2 font-mono text-xs">
                {d.review_status === "pending" ? (
                  <>
                    <button className="text-good hover:underline" onClick={() => act(() => api.setDraftStatus(d.id, "adopted"))}>采纳</button>
                    <button className="text-alert hover:underline" onClick={() => act(() => api.setDraftStatus(d.id, "rejected"))}>否决</button>
                  </>
                ) : <span className="text-muted">{d.review_status}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

Rewrite `frontend/src/pages/AccountDetail.tsx`:
```tsx
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { TrendChart } from "../components/TrendChart";
import { ScoreRadar } from "../components/ScoreRadar";
import { LoopTimeline } from "../components/LoopTimeline";
import { ReviewPanel } from "../components/ReviewPanel";

export function AccountDetail() {
  const { id } = useParams();
  const accountId = Number(id);
  const { data, loading, error, reload } = useAsync(() => api.getAccount(accountId), [accountId]);

  if (loading) return <div className="font-mono text-muted">加载中…</div>;
  if (error || !data) return <div className="font-mono text-alert">加载失败：{error}</div>;

  const latestSnap = [...data.snapshots].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const latestRun = [...data.loop_runs].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const score = latestRun?.evaluation?.composite_score ?? null;

  const runLoop = async () => { await api.triggerLoop(accountId); reload(); };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="font-mono text-xs text-muted">{data.platform} · {data.vertical ?? "—"}</div>
          <h1 className="font-display text-2xl">{data.handle}</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="font-mono text-[11px] uppercase text-muted">价值分</div>
            <div className="font-display text-4xl text-accent tabnums">{score != null ? score.toFixed(0) : "—"}</div>
          </div>
          <button onClick={runLoop} className="font-mono text-xs border border-accent text-accent rounded px-3 py-2 hover:bg-accent hover:text-bg transition">跑一轮 Loop</button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-sm">
        <Kpi label="粉丝" value={latestSnap?.followers?.toLocaleString() ?? "—"} />
        <Kpi label="互动率" value={latestSnap?.engagement_rate != null ? `${(latestSnap.engagement_rate * 100).toFixed(1)}%` : "—"} />
        <Kpi label="爆文率" value={latestSnap?.hit_rate != null ? `${(latestSnap.hit_rate * 100).toFixed(0)}%` : "—"} />
        <Kpi label="转化" value={String(latestSnap?.conversions ?? "—")} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="涨粉趋势"><TrendChart snapshots={data.snapshots} /></Panel>
        <Panel title="评估拆解">{latestRun?.evaluation ? <ScoreRadar breakdown={latestRun.evaluation.breakdown} /> : <Empty />}</Panel>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Loop 历史">{data.loop_runs.length ? <LoopTimeline runs={data.loop_runs} /> : <Empty />}</Panel>
        <Panel title="本轮待审产出">{latestRun ? <ReviewPanel run={latestRun} onChange={reload} /> : <Empty />}</Panel>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="text-[11px] uppercase text-muted">{label}</div>
      <div className="text-lg mt-1 tabnums">{value}</div>
    </div>
  );
}
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4 rise">
      <h2 className="font-display text-sm mb-3">{title}</h2>
      {children}
    </section>
  );
}
function Empty() { return <p className="font-mono text-xs text-muted">暂无数据，点「跑一轮 Loop」。</p>; }
```

- [ ] **Step 4: 运行确认通过 + 全量测试 + build**

Run:
```bash
cd /Users/aa00102/matrix-loop/frontend && npx vitest run 2>&1 | tail -6 && npm run build 2>&1 | tail -3
```
Expected: 全部前端测试 PASS（client 3 + Overview 1 + Detail 1 = 5）且 `npm run build` 成功

- [ ] **Step 5: 提交**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src
git commit -m "feat(dashboard): account detail - score, KPIs, ECharts trend+radar, loop timeline, review panel"
```

---

## 完成标准（本计划）

- `cd frontend && npm run build` 编译通过（tsc 严格模式 + vite build 产出 dist）
- `npx vitest run` 全绿（5 个前端 smoke 测试）
- 两页可用并接后端 API：总览（stat tiles + 需介入队列 + 可排序账号表）、下钻（价值分 + KPI + 趋势/雷达 + Loop 历史 + 采纳/否决审核 + 跑一轮 Loop）
- 深色指挥台美学落地（青柠强调、IBM Plex Mono 数字、Archivo 标题、噪点底、状态点微光）
- 备注：总览「待办队列」v1 只按 `no_progress` 状态；精确的待审草稿/建议计数需后续 `/queue` 端点（留待 plan 8）。视觉最终由浏览器截图人工核验（后端 `uvicorn` + 前端 `npm run dev`）。
