# Video Workbench Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single `/video` "视频工作台" page where a human drives the whole video loop for a selected account: set the `ChannelBrief` (定调), walk a topic → script → video generation flow (each gated by human approval), review finished videos, and watch usage — all wired to the existing backend endpoints, matching the existing dark BI aesthetic.

**Architecture:** One new page (`Video.tsx`) composed of small cards (usage panel, brief editor, draft workflow, review queue), plus a nav item + route. New `api` client methods + TS types front the existing endpoints (`/accounts/{id}/brief`, `/drafts/{id}/generate-script`, `/accounts/{id}/generate-video`, `/video-assets`, `/video-assets/{id}/status`, `/video/usage`, and existing `/accounts/{id}`, `/drafts/{id}/status`). No backend changes.

**Tech Stack:** Vite + React 18 + TypeScript + Tailwind. Tests: vitest + @testing-library/react (stub `fetch`, matching the existing `Flow.test.tsx`/`OpsBar.test.tsx` pattern). Run from `frontend/`.

**Design system (reuse, do not invent):** `ChartCard` (`title`, optional `pill`/`glow`/`className`/`style`, children), `StatTile` (`label`, `value`, optional `accent`), `useAsync(fn, deps) -> {data, loading, error, reload}`, the `api` object + `req<T>`. Tailwind tokens already in use: `bg`, `panel`, `line`, `text`, `muted`, `dim`, `lime`, `cyan`, `violet`, `pink`, `warn`, `alert`, fonts `font-display`/`font-mono`. Follow `Flow.tsx` as the structural reference (page + sub-components in one file, `useAsync`, `ChartCard`, `StatTile`, `withBusy`-style local action state).

Preconditions: on `main`, clean tree, `cd /Users/aa00102/matrix-loop && git checkout -b feat/video-frontend`. Baseline: `cd frontend && npx vitest run` (30 tests pass) and `npx tsc --noEmit` (clean). Git identity `-c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com"`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Backend for manual dogffood runs on :8010 (frontend already points there via `VITE_API_BASE`).

---

## File Structure

- `frontend/src/api/types.ts` (modify) — `ChannelBriefOut`, `VideoAssetOut`, `VideoUsage`.
- `frontend/src/api/client.ts` (modify) — `getBrief`, `setBrief`, `generateScript`, `generateVideo`, `listVideoAssets`, `setVideoReview`, `getVideoUsage`.
- `frontend/src/pages/Video.tsx` (create) — the workbench page + its cards.
- `frontend/src/App.tsx` (modify) — add `/video` route.
- `frontend/src/components/Layout.tsx` (modify) — add "视频" nav item.
- Tests: `frontend/src/pages/Video.test.tsx` (create).

---

### Task 1: Types + API client methods

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Test: (covered by Video.test.tsx in later tasks; this task adds no test of its own — it is pure plumbing verified by `tsc`)

- [ ] **Step 1: Add the types**

Append to `frontend/src/api/types.ts`:

```ts
// ---- Video workbench ----
export interface ChannelBriefOut {
  account_id: number;
  id: number;
  main_direction: string;
  sub_niches: string[];
  tone: string | null;
  language: string;
  persona: string | null;
  format: string;
  compliance_stance: string;
}

export interface VideoAssetOut {
  id: number;
  account_id: number;
  script_draft_id: number | null;
  provider: string;
  media_url: string | null;
  duration: number | null;
  cost: number;
  status: string;
  review_status: string;
  created_at: string;
}

export interface VideoUsage {
  today_count: number;
  today_cost: number;
  total_count: number;
  total_cost: number;
  caps: {
    max_videos_per_day: number;
    per_account_per_day: number;
    per_channel_per_day: number;
    video_budget: number;
  };
}

export interface SetBriefIn {
  main_direction: string;
  sub_niches: string[];
  tone?: string | null;
  language?: string;
  persona?: string | null;
  format?: string;
  compliance_stance?: string;
}
```

- [ ] **Step 2: Add the client methods**

In `frontend/src/api/client.ts`, add these to the imports from `./types`: `ChannelBriefOut, VideoAssetOut, VideoUsage, SetBriefIn, DraftOut`. Then add inside the `api` object (after the flow block):

```ts
  // ---- Video workbench ----
  getBrief: (accountId: number) => req<ChannelBriefOut>(`/accounts/${accountId}/brief`),
  setBrief: (accountId: number, body: SetBriefIn) =>
    req<{ account_id: number; id: number }>(`/accounts/${accountId}/brief`, {
      method: "POST", body: JSON.stringify(body),
    }),
  generateScript: (draftId: number) =>
    req<DraftOut>(`/drafts/${draftId}/generate-script`, { method: "POST" }),
  generateVideo: (accountId: number, scriptDraftId: number) =>
    req<VideoAssetOut>(`/accounts/${accountId}/generate-video`, {
      method: "POST", body: JSON.stringify({ script_draft_id: scriptDraftId }),
    }),
  listVideoAssets: (params?: { account_id?: number; review_status?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.account_id != null) qs.set("account_id", String(params.account_id));
    if (params?.review_status) qs.set("review_status", params.review_status);
    if (params?.status) qs.set("status", params.status);
    const q = qs.toString();
    return req<VideoAssetOut[]>(`/video-assets${q ? `?${q}` : ""}`);
  },
  setVideoReview: (id: number, review_status: string) =>
    req<VideoAssetOut>(`/video-assets/${id}/status`, {
      method: "POST", body: JSON.stringify({ review_status }),
    }),
  getVideoUsage: () => req<VideoUsage>("/video/usage"),
```

(`DraftOut` is already exported from `types.ts`; `req` and the `api` object already exist.)

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0 (no errors). If `DraftOut` was not previously imported in `client.ts`, this is where you confirm the import line is correct.

- [ ] **Step 4: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/api/types.ts frontend/src/api/client.ts
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): video workbench API client methods + types\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Nav item + route + page shell + usage panel

**Files:**
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/Video.tsx`
- Test: `frontend/src/pages/Video.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/Video.test.tsx`:

```tsx
import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Video } from "./Video";

const ACCOUNTS = [
  { id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null,
    latest_followers: 1000, latest_composite_score: 60, latest_loop_status: "ok", source_tier: "api" },
];
const USAGE = {
  today_count: 3, today_cost: 3.0, total_count: 10, total_cost: 10.0,
  caps: { max_videos_per_day: 20, per_account_per_day: 2, per_channel_per_day: 10, video_budget: 20 },
};

function stub(routes: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const custom = routes(String(url), init);
    if (custom !== undefined) return Promise.resolve(custom);
    return Promise.resolve({ ok: true, json: async () => ({}) });
  }));
}

beforeEach(() => {
  stub((url) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    return undefined;
  });
});
afterEach(() => vi.unstubAllGlobals());

it("renders the usage panel from GET /video/usage", async () => {
  render(<MemoryRouter><Video /></MemoryRouter>);
  expect(await screen.findByText(/视频用量/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());   // today_count
});

it("lets the user pick an account", async () => {
  render(<MemoryRouter><Video /></MemoryRouter>);
  const select = await screen.findByLabelText(/选择账号/);
  expect(select).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: FAIL (`Video` does not exist).

- [ ] **Step 3: Create the page shell + usage panel**

Create `frontend/src/pages/Video.tsx`:

```tsx
import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok", twitter: "X",
  weixin_video: "视频号", weixin_gzh: "公众号", youtube: "YouTube", instagram: "IG", bilibili: "B站",
};

export function Video() {
  const accounts = useAsync(() => api.listAccounts(), []);
  const usage = useAsync(() => api.getVideoUsage(), []);
  const [acctId, setAcctId] = useState<number | "">("");

  const u = usage.data;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">
            视频<span className="text-violet">工作台</span>
          </h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">
            定调 → 选题 → 脚本 → 视频 → <span className="text-warn">人审成片</span> → 发布 · 每一步人在环
          </p>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 font-mono text-xs text-muted">
          选择账号
          <select
            aria-label="选择账号"
            className="rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text focus:border-violet focus:outline-none"
            value={acctId}
            onChange={(e) => setAcctId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">选择账号…</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {(PLATFORM_LABEL[a.platform] ?? a.platform)} · {a.handle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* usage panel */}
      <ChartCard title="📊 视频用量" pill={u ? `预算 ${u.caps.video_budget}` : "—"} className="mb-[14px]">
        <div className="grid grid-cols-2 gap-[14px] md:grid-cols-4">
          <StatTile label="今日条数" value={String(u?.today_count ?? 0)} accent />
          <StatTile label="今日成本" value={String(u?.today_cost ?? 0)} />
          <StatTile label="累计条数" value={String(u?.total_count ?? 0)} />
          <StatTile label="累计成本" value={String(u?.total_cost ?? 0)} />
        </div>
        <p className="mt-[10px] font-mono text-[10px] leading-relaxed text-dim">
          日上限:全局 {u?.caps.max_videos_per_day ?? "—"} · 单号 {u?.caps.per_account_per_day ?? "—"} · 单垂类 {u?.caps.per_channel_per_day ?? "—"}
        </p>
      </ChartCard>

      {acctId === "" ? (
        <ChartCard title="👆 先选一个账号">
          <p className="py-8 text-center font-mono text-xs text-muted">选择账号后可设定调、生成脚本/视频、审核成片。</p>
        </ChartCard>
      ) : (
        <div className="grid gap-[14px] lg:grid-cols-2">
          <BriefEditor accountId={acctId} />
          <DraftWorkflow accountId={acctId} onGenerated={() => usage.reload()} />
          <ReviewQueue accountId={acctId} className="lg:col-span-2" />
        </div>
      )}
    </div>
  );
}

// Placeholder sub-components — implemented in Tasks 3-5.
function BriefEditor({ accountId }: { accountId: number }) {
  return <ChartCard title="🎯 频道定调"><div data-testid="brief-editor" /></ChartCard>;
}
function DraftWorkflow({ accountId, onGenerated }: { accountId: number; onGenerated: () => void }) {
  return <ChartCard title="✍️ 选题 · 脚本 · 视频"><div data-testid="draft-workflow" /></ChartCard>;
}
function ReviewQueue({ accountId, className }: { accountId: number; className?: string }) {
  return <ChartCard title="🎬 成片审核" className={className}><div data-testid="review-queue" /></ChartCard>;
}
```

Note: `useMemo` is imported for use in later tasks; if the linter flags it as unused now, add the review-queue memo in Task 5 or drop the import until then. Prefer to keep the import and silence by using it — but if `tsc`/eslint fails on unused, remove it from the import in this task and re-add in Task 5.

- [ ] **Step 4: Add the route + nav**

In `frontend/src/App.tsx`: add `import { Video } from "./pages/Video";` and `<Route path="/video" element={<Video />} />` inside `<Routes>`.

In `frontend/src/components/Layout.tsx`: add to the `NAV` array (after the 导流 entry): `{ to: "/video", label: "视频" },`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit` → exit 0.

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): video workbench page shell + nav + usage panel\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Brief editor

**Files:**
- Modify: `frontend/src/pages/Video.tsx` (replace the `BriefEditor` placeholder)
- Test: `frontend/src/pages/Video.test.tsx` (extend)

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Video.test.tsx`:

```tsx
const BRIEF = {
  account_id: 4, id: 1, main_direction: "web3",
  sub_niches: ["空投猎人", "DeFi"], tone: "punchy", language: "en",
  persona: "Nina", format: "faceless", compliance_stance: "info_education",
};

it("loads an existing brief into the editor", async () => {
  stub((url) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: true, json: async () => BRIEF };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => ({ id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null, objective_weights: {}, snapshots: [], content_items: [], loop_runs: [] }) };
    return undefined;
  });
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  // select account 4
  const select = await screen.findByLabelText(/选择账号/);
  const { fireEvent } = await import("@testing-library/react");
  fireEvent.change(select, { target: { value: "4" } });
  // brief main_direction shows up in the editor input
  await waitFor(() => {
    const input = screen.getByDisplayValue("web3");
    expect(input).toBeInTheDocument();
  });
  expect(screen.getByDisplayValue("Nina")).toBeInTheDocument();
});

it("saves the brief via POST /accounts/{id}/brief", async () => {
  const posted: RequestInit[] = [];
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/) && init?.method === "POST") {
      posted.push(init); return { ok: true, json: async () => ({ account_id: 4, id: 1 }) };
    }
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({ detail: "no brief" }) };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => ({ id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null, objective_weights: {}, snapshots: [], content_items: [], loop_runs: [] }) };
    return undefined;
  });
  const { fireEvent } = await import("@testing-library/react");
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  const mainInput = await screen.findByPlaceholderText(/主方向/);
  fireEvent.change(mainInput, { target: { value: "web3" } });
  fireEvent.click(screen.getByRole("button", { name: /保存定调/ }));
  await waitFor(() => expect(posted.length).toBe(1));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: FAIL (editor has no inputs / no 保存定调 button).

- [ ] **Step 3: Implement `BriefEditor`**

In `frontend/src/pages/Video.tsx`, replace the `BriefEditor` placeholder with:

```tsx
function BriefEditor({ accountId }: { accountId: number }) {
  const brief = useAsync(() => api.getBrief(accountId).catch(() => null), [accountId]);
  const [main, setMain] = useState("");
  const [niches, setNiches] = useState("");
  const [tone, setTone] = useState("");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState("en");
  const [format, setFormat] = useState("faceless");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadedFor, setLoadedFor] = useState<number | null>(null);

  // hydrate the form once the brief for this account arrives
  if (!brief.loading && loadedFor !== accountId) {
    const b = brief.data;
    setMain(b?.main_direction ?? "");
    setNiches((b?.sub_niches ?? []).join("、"));
    setTone(b?.tone ?? "");
    setPersona(b?.persona ?? "");
    setLanguage(b?.language ?? "en");
    setFormat(b?.format ?? "faceless");
    setLoadedFor(accountId);
  }

  async function save() {
    setBusy(true); setMsg(null);
    try {
      await api.setBrief(accountId, {
        main_direction: main.trim(),
        sub_niches: niches.split(/[、,，]/).map((s) => s.trim()).filter(Boolean),
        tone: tone.trim() || null,
        persona: persona.trim() || null,
        language,
        format,
      });
      setMsg("已保存定调");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  const inputCls = "w-full rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text placeholder:text-muted focus:border-violet focus:outline-none";

  return (
    <ChartCard title="🎯 频道定调">
      <div className="space-y-[10px]">
        <input className={inputCls} placeholder="主方向,如 web3" value={main} onChange={(e) => setMain(e.target.value)} />
        <input className={inputCls} placeholder="子垂类(顿号分隔),如 加密交易者、空投猎人、DeFi" value={niches} onChange={(e) => setNiches(e.target.value)} />
        <div className="flex gap-2">
          <input className={inputCls} placeholder="人设,如 Nina" value={persona} onChange={(e) => setPersona(e.target.value)} />
          <input className={inputCls} placeholder="语气,如 punchy" value={tone} onChange={(e) => setTone(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <select className={inputCls} value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
          <select className={inputCls} value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="faceless">faceless 口播</option>
            <option value="avatar">数字人</option>
          </select>
        </div>
        <button
          onClick={save}
          disabled={busy}
          className="rounded-lg border border-violet/50 bg-violet/[.1] px-4 py-2 font-mono text-xs text-violet transition-colors hover:bg-violet/[.18] disabled:opacity-50"
        >
          {busy ? "保存中…" : "保存定调"}
        </button>
        {msg && <p className="font-mono text-[11px] text-muted">{msg}</p>}
      </div>
    </ChartCard>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: PASS (4 tests total).

- [ ] **Step 5: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit` → exit 0.

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): ChannelBrief editor on the video workbench\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Draft workflow (topic → script → video, human-gated)

**Files:**
- Modify: `frontend/src/pages/Video.tsx` (replace the `DraftWorkflow` placeholder)
- Test: `frontend/src/pages/Video.test.tsx` (extend)

The workflow reads the account's drafts from `GET /accounts/{id}` (drafts are nested in `loop_runs[].drafts`), flattened newest-first. Per draft:
- `kind==="topic"`, `review_status!=="adopted"`: show "采纳选题" (→ `setDraftStatus(id, "adopted")`).
- `kind==="topic"`, adopted: show "生成脚本" (→ `generateScript(id)`).
- `kind==="script"`, not adopted: show "采纳脚本".
- `kind==="script"`, adopted: show "生成视频" (→ `generateVideo(accountId, id)`).

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Video.test.tsx`:

```tsx
function detailWithDrafts(drafts: { id: number; kind: string; content: string; review_status: string }[]) {
  return {
    id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null,
    objective_weights: {}, snapshots: [], content_items: [],
    loop_runs: [{ id: 1, ts: "2026-07-09T00:00:00Z", diagnosis: "d", verify_result: {}, status: "ok",
      evaluation: null, recommendations: [], drafts }],
  };
}

it("adopts a topic then generates a script", async () => {
  const calls: string[] = [];
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/drafts\/1\/status$/) && init?.method === "POST") { calls.push("adopt-topic"); return { ok: true, json: async () => ({}) }; }
    if (url.match(/\/drafts\/1\/generate-script$/) && init?.method === "POST") { calls.push("gen-script"); return { ok: true, json: async () => ({ id: 2, kind: "script", content: "Hook...", review_status: "pending" }) }; }
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([{ id: 1, kind: "topic", content: "Airdrop 101", review_status: "adopted" }]) };
    return undefined;
  });
  const { fireEvent } = await import("@testing-library/react");
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  // adopted topic -> 生成脚本 button present
  fireEvent.click(await screen.findByRole("button", { name: /生成脚本/ }));
  await waitFor(() => expect(calls).toContain("gen-script"));
});

it("generates a video from an adopted script", async () => {
  const calls: string[] = [];
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/accounts\/4\/generate-video$/) && init?.method === "POST") { calls.push("gen-video"); return { ok: true, json: async () => ({ id: 9, account_id: 4, script_draft_id: 2, provider: "fake", media_url: "https://f/x.mp4", duration: 45, cost: 1, status: "ready", review_status: "pending", created_at: "2026-07-09T00:00:00Z" }) }; }
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([{ id: 2, kind: "script", content: "Hook...", review_status: "adopted" }]) };
    return undefined;
  });
  const { fireEvent } = await import("@testing-library/react");
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  fireEvent.click(await screen.findByRole("button", { name: /生成视频/ }));
  await waitFor(() => expect(calls).toContain("gen-video"));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: FAIL (no workflow buttons).

- [ ] **Step 3: Implement `DraftWorkflow`**

In `frontend/src/pages/Video.tsx`, replace the `DraftWorkflow` placeholder with (and add `import type { DraftOut } from "../api/types";` at the top):

```tsx
function DraftWorkflow({ accountId, onGenerated }: { accountId: number; onGenerated: () => void }) {
  const detail = useAsync(() => api.getAccount(accountId), [accountId]);
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const drafts: DraftOut[] = useMemo(() => {
    const runs = detail.data?.loop_runs ?? [];
    const all = runs.flatMap((r) => r.drafts ?? []);
    return [...all].reverse();   // newest first
  }, [detail.data]);

  async function act(key: number, fn: () => Promise<unknown>, done: string) {
    setBusy(key); setMsg(null);
    try { await fn(); setMsg(done); detail.reload(); onGenerated(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(null); }
  }

  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <ChartCard title="✍️ 选题 · 脚本 · 视频" pill={`${drafts.length} 草稿`}>
      {drafts.length === 0 && (
        <p className="py-6 text-center font-mono text-[11px] text-muted">
          还没有草稿。先在总览/下钻里对该账号跑一轮 Loop 生成选题。
        </p>
      )}
      <div className="space-y-[8px]">
        {drafts.map((d) => {
          const adopted = d.review_status === "adopted";
          return (
            <div key={d.id} className="rounded-lg border border-line bg-panel px-3 py-2">
              <div className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
                <span className={d.kind === "script" ? "text-cyan" : "text-lime"}>{d.kind}</span>
                <span className="text-dim">#{d.id}</span>
                <span className="text-muted">{d.review_status}</span>
              </div>
              <p className="mb-2 font-mono text-[11px] leading-relaxed text-text">{d.content.slice(0, 200)}</p>
              <div className="flex gap-2">
                {!adopted && (
                  <button className={`${btn} border-muted/40 text-muted hover:text-text`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.setDraftStatus(d.id, "adopted"), "已采纳")}>
                    采纳{d.kind === "script" ? "脚本" : "选题"}
                  </button>
                )}
                {adopted && d.kind === "topic" && (
                  <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.generateScript(d.id), "已生成脚本")}>
                    {busy === d.id ? "生成中…" : "生成脚本"}
                  </button>
                )}
                {adopted && d.kind === "script" && (
                  <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.generateVideo(accountId, d.id), "已生成视频")}>
                    {busy === d.id ? "生成中…" : "生成视频"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {msg && <p className="mt-2 font-mono text-[11px] text-muted">{msg}</p>}
    </ChartCard>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: PASS (6 tests total).

- [ ] **Step 5: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit` → exit 0.

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): human-gated topic->script->video workflow on the workbench\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 5: Review queue

**Files:**
- Modify: `frontend/src/pages/Video.tsx` (replace the `ReviewQueue` placeholder)
- Test: `frontend/src/pages/Video.test.tsx` (extend)

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Video.test.tsx`:

```tsx
const ASSET = {
  id: 9, account_id: 4, script_draft_id: 2, provider: "fake", media_url: "https://fake.local/v/x.mp4",
  duration: 45, cost: 1, status: "ready", review_status: "pending", created_at: "2026-07-09T00:00:00Z",
};

it("lists video assets and approves one", async () => {
  const calls: Array<{ url: string; body: string }> = [];
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([]) };
    if (url.match(/\/video-assets\/9\/status$/) && init?.method === "POST") {
      calls.push({ url: String(url), body: String(init?.body) });
      return { ok: true, json: async () => ({ ...ASSET, review_status: "approved" }) };
    }
    if (url.includes("/video-assets")) return { ok: true, json: async () => [ASSET] };
    return undefined;
  });
  const { fireEvent } = await import("@testing-library/react");
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  // asset row shows provider + a link to the media
  expect(await screen.findByText(/fake/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /通过/ }));
  await waitFor(() => expect(calls.length).toBe(1));
  expect(calls[0].body).toContain("approved");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: FAIL (review queue empty placeholder).

- [ ] **Step 3: Implement `ReviewQueue`**

In `frontend/src/pages/Video.tsx`, replace the `ReviewQueue` placeholder with (and add `import type { VideoAssetOut } from "../api/types";` to the top type import):

```tsx
function ReviewQueue({ accountId, className }: { accountId: number; className?: string }) {
  const assets = useAsync(() => api.listVideoAssets({ account_id: accountId }), [accountId]);
  const [busy, setBusy] = useState<number | null>(null);

  async function review(id: number, status: string) {
    setBusy(id);
    try { await api.setVideoReview(id, status); assets.reload(); }
    finally { setBusy(null); }
  }

  const rows: VideoAssetOut[] = assets.data ?? [];
  const badge: Record<string, string> = {
    pending: "text-warn", approved: "text-good", rejected: "text-alert",
  };
  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <ChartCard title="🎬 成片审核" pill={`${rows.length} 条`} className={className}>
      {rows.length === 0 && (
        <p className="py-6 text-center font-mono text-[11px] text-muted">该账号还没有成片。生成后在这里审核。</p>
      )}
      <div className="space-y-[8px]">
        {rows.map((v) => (
          <div key={v.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel px-3 py-2">
            <span className="font-mono text-[11px] text-dim">#{v.id}</span>
            <span className="font-mono text-[11px] text-muted">{v.provider}</span>
            <span className={`font-mono text-[11px] ${badge[v.review_status] ?? "text-muted"}`}>{v.review_status}</span>
            <span className="font-mono text-[10px] text-dim">成本 {v.cost}</span>
            {v.media_url && (
              <a href={v.media_url} target="_blank" rel="noreferrer"
                className="font-mono text-[11px] text-cyan underline decoration-dotted hover:text-cyan/80">看成片</a>
            )}
            <div className="flex-1" />
            {v.review_status === "pending" && (
              <>
                <button className={`${btn} border-good/50 bg-good/[.08] text-good`} disabled={busy === v.id}
                  onClick={() => review(v.id, "approved")}>通过</button>
                <button className={`${btn} border-alert/50 bg-alert/[.08] text-alert`} disabled={busy === v.id}
                  onClick={() => review(v.id, "rejected")}>否决</button>
              </>
            )}
          </div>
        ))}
      </div>
    </ChartCard>
  );
}
```

Also: now that Task 5 uses `useMemo` (Task 4) and both `DraftOut`/`VideoAssetOut` type imports exist, confirm the top of `Video.tsx` imports are: `import { useMemo, useState } from "react";` and `import type { DraftOut, VideoAssetOut } from "../api/types";`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Video.test.tsx`
Expected: PASS (7 tests total).

- [ ] **Step 5: Full frontend suite + typecheck**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: no type errors; all pass (30 baseline + 7 new = 37).

- [ ] **Step 6: Commit**

```bash
cd /Users/aa00102/matrix-loop
git add frontend/src/pages/Video.tsx frontend/src/pages/Video.test.tsx
git -c user.name="aa00102" -c user.email="mingjia.tian@elevatesphere.com" commit -m "$(printf 'feat(fe): finished-video review queue on the workbench\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## After all tasks

- Dispatch a final code review over the branch diff (`git diff main..HEAD -- frontend/`).
- Use `superpowers:finishing-a-development-branch` to merge to `main` (option 1, `--no-ff`).
- Live dogfood (manual): frontend :5173 → :8010, open `/video`, pick @money_talk, set 定调, run a loop from Overview to get topics, then adopt → 生成脚本 → adopt → 生成视频 → review; watch 视频用量 tick.

## Self-review notes (against the design)

- **Coverage:** brief editor (Task 3), topic→script→video human-gated workflow (Task 4), review queue with approve/reject (Task 5), usage panel + nav/route (Task 2), types+client (Task 1). All wired to existing endpoints; no backend change.
- **Type consistency:** `api.getBrief/setBrief/generateScript/generateVideo/listVideoAssets/setVideoReview/getVideoUsage` signatures match the client methods (Task 1) and their call sites (Tasks 3-5); `ChannelBriefOut`/`VideoAssetOut`/`VideoUsage`/`SetBriefIn` fields match the backend schemas (`SetBrief`, `VideoAssetOut`, `usage_summary`).
- **No placeholders:** every step has full code, exact commands, expected outcomes. (The Task 2 sub-component stubs are explicitly replaced in Tasks 3-5.)
- **Human-in-loop preserved in the UI:** 生成脚本 only appears on an adopted topic; 生成视频 only on an adopted script; videos land as `pending` and require an explicit 通过/否决.
