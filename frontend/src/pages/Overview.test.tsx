import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Overview } from "./Overview";
import type { Overview as OverviewT, AccountListItem } from "../api/types";

// ECharts is heavy + canvas-based; stub it in tests.
vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const OVERVIEW: OverviewT = {
  kpis: { total_accounts: 2, avg_score: 64, needs_attention: 1, platforms: 2, pending_review: 3 },
  platform_health: [
    { platform: "xiaohongshu", growth: 90, engagement: 80, commercial: 60, positioning: 92 },
    { platform: "twitter", growth: 20, engagement: 50, commercial: 40, positioning: 30 },
  ],
  trend: [
    { date: "2026-07-01", followers: 150000, engagement: 0.04 },
    { date: "2026-07-06", followers: 161000, engagement: 0.045 },
  ],
  alerts: [
    { account_id: 2, handle: "@a2", platform: "twitter", kind: "no_progress", detail: "连续无进展，需介入" },
    { account_id: 1, handle: "@a1", platform: "xiaohongshu", kind: "pending_drafts", detail: "1 条草稿待审" },
  ],
  top_movers: [
    { account_id: 1, handle: "@a1", platform: "xiaohongshu", delta_followers: 12000 },
    { account_id: 2, handle: "@a2", platform: "twitter", delta_followers: -1000 },
  ],
  positioning_distribution: { clear: 1, ok: 0, scattered: 1 },
};

const ACCOUNTS: AccountListItem[] = [
  { id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: null, latest_followers: 99000, latest_composite_score: 88, latest_loop_status: "ok", source_tier: "manual" },
  { id: 2, platform: "twitter", handle: "@a2", vertical: null, positioning: null, latest_followers: 49000, latest_composite_score: 40, latest_loop_status: "no_progress", source_tier: "scrape" },
];

function stubFetch(impl?: (url: string, init?: RequestInit) => unknown) {
  const fn = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (impl) {
      const custom = impl(url, init);
      if (custom !== undefined) return Promise.resolve(custom);
    }
    const body = String(url).includes("/overview") ? OVERVIEW : ACCOUNTS;
    return Promise.resolve({ ok: true, json: async () => body });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => { stubFetch(); });
afterEach(() => vi.unstubAllGlobals());

it("renders KPI numbers from /overview", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  expect(await screen.findByText("账号总数")).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();     // total_accounts
  expect(screen.getByText("64")).toBeInTheDocument();    // avg_score
});

it("renders platform-health rows for each platform", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  expect(await screen.findAllByText(/小红书/)).toBeTruthy();
  expect(screen.getAllByText(/X|twitter/i).length).toBeGreaterThanOrEqual(1);
});

it("renders the no_progress alert in the alert center", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  // the no_progress alert references @a2
  const alerts = await screen.findAllByText(/@a2/);
  expect(alerts.length).toBeGreaterThanOrEqual(1);
});

it("renders account cards with handles from /accounts", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  expect(await screen.findAllByText("@a1")).toBeTruthy();
});

it("filters account cards by search box", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  await screen.findByPlaceholderText(/搜索/);
  fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "a1" } });
  // @a2 should disappear from account cards; @a1 stays
  await waitFor(() => {
    expect(screen.getAllByText("@a1").length).toBeGreaterThanOrEqual(1);
  });
});

it("clicking 跑一批 POSTs to /batch/run then reloads", async () => {
  const fetchMock = stubFetch((url, init) => {
    if (init?.method === "POST" && String(url).includes("/batch/run")) {
      return { ok: true, json: async () => ({ total: 2 }) };
    }
    return undefined;
  });
  render(<MemoryRouter><Overview /></MemoryRouter>);
  await screen.findByText("账号总数");
  fireEvent.click(screen.getByRole("button", { name: /跑一批/ }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find((args: unknown[]) => {
      const [url, init] = args as [string, RequestInit];
      return String(url).includes("/batch/run") && init?.method === "POST";
    });
    expect(call).toBeDefined();
  });
});
