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
