import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Flywheel } from "./Flywheel";
import type { FlywheelAccountLive, FlywheelEventLive, FlywheelState } from "../api/types";

const STATE: FlywheelState = {
  paused: false, autopilot_accounts: 5, pending_review: 2,
  steps: [], accounts: [], events: [],
  today_cost: 1.18, status_counts: { running: 2, blocked: 1, ok: 2 },
};

const ACCOUNTS: FlywheelAccountLive[] = [
  {
    account_id: 4, platform: "twitter", handle: "@money_talk", autopilot: true,
    status: "running", current_step: "video", step_index: 4, steps_done: 4,
    elapsed_sec: 102, blocked_reason: null,
    last_event: { step: "video", status: "running", detail: null, ts: "2026-07-09T21:02:00+00:00" },
    kpis: { followers: 12400, followers_delta: 2.1, views_7d: 86200, score: 78 },
    cost_cycle: 0.42, next_run_eta_sec: null, synced_at: "2026-07-09T21:00:00+00:00",
  },
];

const EVENTS: FlywheelEventLive[] = [
  { id: 9, account_id: 4, account_handle: "@money_talk", step: "script", status: "ok", detail: "生成《Fed》", ts: "2026-07-09T21:02:00+00:00" },
];

function stub(routes: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const c = routes(String(url), init);
    return Promise.resolve(c !== undefined ? c : { ok: true, json: async () => ({}) });
  }));
}

function defaultRoutes(url: string): unknown {
  if (url.endsWith("/flywheel/accounts")) return { ok: true, json: async () => ACCOUNTS };
  if (url.endsWith("/flywheel")) return { ok: true, json: async () => STATE };
  if (url.includes("/flywheel/events")) return { ok: true, json: async () => EVENTS };
  return undefined;
}

beforeEach(() => { stub(defaultRoutes); });
afterEach(() => vi.unstubAllGlobals());

it("renders account cards from /flywheel/accounts and header stats from /flywheel", async () => {
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  // header stats (unique to /flywheel)
  expect(await screen.findByText("$1.18")).toBeInTheDocument();
  // account handle appears in the card (and in the feed) -> at least one
  expect(screen.getAllByText("@money_talk").length).toBeGreaterThan(0);
  await waitFor(() => expect(screen.getByText("实时 · 4s")).toBeInTheDocument());
});

it("renders live events from /flywheel/events", async () => {
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  expect(await screen.findByText(/生成《Fed》/)).toBeInTheDocument();
});

it("shows empty state when there are no autopilot accounts", async () => {
  stub((url) => {
    if (url.endsWith("/flywheel/accounts")) return { ok: true, json: async () => [] };
    return defaultRoutes(url);
  });
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  expect(await screen.findByText("暂无自动驾驶账号")).toBeInTheDocument();
});

it("pause button calls POST /flywheel/pause", async () => {
  const calls: string[] = [];
  stub((url, init) => {
    if (url.endsWith("/flywheel/pause") && init?.method === "POST") { calls.push("pause"); return { ok: true, json: async () => ({ paused: true }) }; }
    return defaultRoutes(url);
  });
  render(<MemoryRouter><Flywheel /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: /暂停或恢复飞轮/ }));
  await waitFor(() => expect(calls).toContain("pause"));
});
