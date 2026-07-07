import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Flow } from "./Flow";
import type { FlowData, AccountListItem } from "../api/types";

// ECharts is heavy + canvas-based; stub it so we can assert the sankey renders.
vi.mock("echarts-for-react", () => ({
  default: (props: { option?: unknown }) => (
    <div data-testid="echart" data-option={JSON.stringify(props.option ?? {})} />
  ),
}));

const FLOW: FlowData = {
  nodes: [
    { name: "acct:@money_talk" },
    { name: "acct:@beauty_lab" },
    { name: "seg:crypto" },
    { name: "seg:海外投资者" },
    { name: "seg:宝妈" },
    { name: "ep:Nina" },
    { name: "ep:xaue" },
    { name: "ep:未定向" },
  ],
  links: [
    { source: "acct:@money_talk", target: "seg:crypto", value: 6000 },
    { source: "acct:@money_talk", target: "seg:海外投资者", value: 4000 },
    { source: "seg:crypto", target: "ep:Nina", value: 6000 },
    { source: "seg:海外投资者", target: "ep:Nina", value: 4000 },
    { source: "acct:@beauty_lab", target: "seg:宝妈", value: 5000 },
    { source: "seg:宝妈", target: "ep:未定向", value: 5000 },
  ],
};

const ACCOUNTS: AccountListItem[] = [
  { id: 4, platform: "twitter", handle: "@money_talk", vertical: "finance", positioning: null, latest_followers: 219000, latest_composite_score: 70, latest_loop_status: "ok", source_tier: "api" },
  { id: 1, platform: "xiaohongshu", handle: "@beauty_lab", vertical: "beauty", positioning: null, latest_followers: 99000, latest_composite_score: 88, latest_loop_status: "ok", source_tier: "manual" },
];

function stubFetch(impl?: (url: string, init?: RequestInit) => unknown) {
  const fn = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (impl) {
      const custom = impl(url, init);
      if (custom !== undefined) return Promise.resolve(custom);
    }
    const u = String(url);
    if (u.includes("/flow")) return Promise.resolve({ ok: true, json: async () => FLOW });
    if (u.includes("/accounts")) return Promise.resolve({ ok: true, json: async () => ACCOUNTS });
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => { stubFetch(); });
afterEach(() => vi.unstubAllGlobals());

it("renders the sankey chart from /flow", async () => {
  render(<MemoryRouter><Flow /></MemoryRouter>);
  const chart = await screen.findByTestId("echart");
  expect(chart).toBeInTheDocument();
  const opt = JSON.parse(chart.getAttribute("data-option") ?? "{}");
  expect(opt.series?.[0]?.type).toBe("sankey");
  // prefixes stripped for display labels
  const nodeNames = (opt.series?.[0]?.data ?? []).map((n: { name: string }) => n.name);
  expect(nodeNames).toContain("@money_talk");
  expect(nodeNames).toContain("crypto");
  expect(nodeNames).toContain("Nina");
});

it("renders summary stats (node/link/total flow counts)", async () => {
  render(<MemoryRouter><Flow /></MemoryRouter>);
  // total flow = sum of account->segment link values = 6000+4000+5000 = 15000
  expect(await screen.findByText(/15,?000/)).toBeInTheDocument();
  // stat labels are present (账号 appears in both a StatTile and the legend)
  expect(screen.getAllByText("账号").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("人群标签")).toBeInTheDocument();
  expect(screen.getByText("变现出口")).toBeInTheDocument();
});

it("shows the honest disclaimer note", async () => {
  render(<MemoryRouter><Flow /></MemoryRouter>);
  expect(await screen.findByText(/非真实转化/)).toBeInTheDocument();
});

it("creates an audience segment via the config panel", async () => {
  const fetchMock = stubFetch((url, init) => {
    if (init?.method === "POST" && String(url).includes("/segments") && !String(url).includes("/accounts/")) {
      return { ok: true, json: async () => ({ id: 99, label: "打工人群" }) };
    }
    return undefined;
  });
  render(<MemoryRouter><Flow /></MemoryRouter>);
  await screen.findByTestId("echart");
  fireEvent.change(screen.getByPlaceholderText(/新建人群标签/), { target: { value: "打工人群" } });
  fireEvent.click(screen.getByRole("button", { name: /加人群/ }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find((args: unknown[]) => {
      const [u, i] = args as [string, RequestInit];
      return String(u).includes("/segments") && !String(u).includes("/accounts/") && i?.method === "POST";
    });
    expect(call).toBeDefined();
  });
});

it("shows an empty state prompting to reset when flow is empty", async () => {
  stubFetch((url) => {
    if (String(url).includes("/flow")) return { ok: true, json: async () => ({ nodes: [], links: [] }) };
    return undefined;
  });
  render(<MemoryRouter><Flow /></MemoryRouter>);
  // empty-state prompt is the load-bearing assertion; reset buttons appear in both
  // the empty state and the config panel, so assert the prompt copy directly.
  expect(await screen.findByText(/还没有导流数据/)).toBeInTheDocument();
  expect(screen.getAllByText(/重置为示例/).length).toBeGreaterThanOrEqual(1);
});
