import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Compare } from "./Compare";
import type { AccountListItem, AccountDetail } from "../api/types";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const ACCOUNTS: AccountListItem[] = [
  { id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: null, latest_followers: 99000, latest_composite_score: 88, latest_loop_status: "ok", source_tier: "manual" },
  { id: 2, platform: "twitter", handle: "@a2", vertical: "tech", positioning: null, latest_followers: 49000, latest_composite_score: 40, latest_loop_status: "no_progress", source_tier: "scrape" },
];

function detail(id: number, handle: string, score: number): AccountDetail {
  return {
    id, platform: id === 1 ? "xiaohongshu" : "twitter", handle, vertical: "v", positioning: "p",
    objective_weights: { growth: 0.4, engagement: 0.3, commercial: 0.2, positioning: 0.1 },
    snapshots: [
      { id: id * 10, ts: "2026-07-01T00:00:00+00:00", followers: 90000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 2, source_tier: "manual" },
      { id: id * 10 + 1, ts: "2026-07-06T00:00:00+00:00", followers: 99000, engagement_rate: 0.06, hit_rate: 0.12, conversions: 3, source_tier: "manual" },
    ],
    content_items: [],
    loop_runs: [
      { id: id * 100, ts: "2026-07-06T01:00:00+00:00", diagnosis: "d", verify_result: { delta: 5 }, status: "ok",
        evaluation: { id: id * 1000, composite_score: score, breakdown: { growth: 90, engagement: 80, commercial: 60, positioning: 70 }, created_at: "2026-07-06T01:00:00+00:00" },
        recommendations: [], drafts: [] },
    ],
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const u = String(url);
    if (u.endsWith("/accounts/1")) return Promise.resolve({ ok: true, json: async () => detail(1, "@a1", 88) });
    if (u.endsWith("/accounts/2")) return Promise.resolve({ ok: true, json: async () => detail(2, "@a2", 40) });
    return Promise.resolve({ ok: true, json: async () => ACCOUNTS });
  }));
});
afterEach(() => vi.unstubAllGlobals());

it("renders a prompt/empty state when no ids are given", async () => {
  render(
    <MemoryRouter initialEntries={["/compare"]}>
      <Compare />
    </MemoryRouter>,
  );
  // No selection: Compare must not crash and shows the pick-accounts prompt.
  expect(await screen.findByText(/选 2-3 个账号开始对比/)).toBeInTheDocument();
});

it("renders a single column for ?ids=1 without crashing", async () => {
  render(
    <MemoryRouter initialEntries={["/compare?ids=1"]}>
      <Compare />
    </MemoryRouter>,
  );
  // @a1 also renders as a picker chip, so assert on the column's unique value
  // score (88 comes from account 1's loop evaluation, rendered only in the column).
  expect(await screen.findByText("88")).toBeInTheDocument();
});

it("renders both selected accounts side by side (?ids=1,2)", async () => {
  render(
    <MemoryRouter initialEntries={["/compare?ids=1,2"]}>
      <Compare />
    </MemoryRouter>,
  );
  // both columns render their handle
  expect(await screen.findAllByText("@a1")).toBeTruthy();
  expect(await screen.findAllByText("@a2")).toBeTruthy();
  // both value scores appear
  expect(await screen.findByText("88")).toBeInTheDocument();
  expect(await screen.findByText("40")).toBeInTheDocument();
});
