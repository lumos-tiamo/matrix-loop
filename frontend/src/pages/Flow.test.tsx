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
    if (u.includes("/demo/reset")) return Promise.resolve({ ok: true, json: async () => ({ endpoints: 2, segments: 4, routed: 5 }) });
    // GET pool routes (POST create routes fall through to caller-provided impl or the {} default)
    if (u.endsWith("/segments") && init?.method !== "POST") return Promise.resolve({ ok: true, json: async () => [] as unknown });
    if (u.endsWith("/endpoints") && init?.method !== "POST") return Promise.resolve({ ok: true, json: async () => [] as unknown });
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
  // node identity uses full prefixed strings to avoid collisions (e.g. ep:Nina vs acct:Nina)
  const nodeNames = (opt.series?.[0]?.data ?? []).map((n: { name: string }) => n.name);
  expect(nodeNames).toContain("acct:@money_talk");
  expect(nodeNames).toContain("seg:crypto");
  expect(nodeNames).toContain("ep:Nina");
  // links also use full prefixed strings
  const linkSources = (opt.series?.[0]?.links ?? []).map((l: { source: string }) => l.source);
  expect(linkSources).toContain("acct:@money_talk");
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

it("segment-only save does NOT call setEndpoint but DOES call setComposition", async () => {
  // Stub: createSegment returns id=77, setComposition and getFlow/accounts all ok
  const fetchMock = stubFetch((url, init) => {
    const u = String(url);
    // createSegment POST
    if (init?.method === "POST" && u.includes("/segments") && !u.includes("/accounts/")) {
      return { ok: true, json: async () => ({ id: 77, label: "测试人群" }) };
    }
    return undefined; // fallthrough to default (flow/accounts ok stubs)
  });

  render(<MemoryRouter><Flow /></MemoryRouter>);
  // Wait for the page to load (echart rendered means flow+accounts fetched)
  await screen.findByTestId("echart");

  // Create a segment so the segment pool is populated
  fireEvent.change(screen.getByPlaceholderText(/新建人群标签/), { target: { value: "测试人群" } });
  fireEvent.click(screen.getByRole("button", { name: /加人群/ }));
  // Wait for the segment chip to appear
  await screen.findByText("测试人群");

  // Pick an account (id=4) — use the first select (account picker)
  const allSelects = document.querySelectorAll("select");
  // First select is the account picker
  fireEvent.change(allSelects[0], { target: { value: "4" } });

  // Toggle the segment on (do NOT touch the endpoint select)
  fireEvent.click(screen.getByRole("button", { name: "测试人群" }));

  // Click 保存配置 — no endpoint select touched so epTouched=false
  fireEvent.click(screen.getByRole("button", { name: /保存配置/ }));

  await waitFor(() => {
    const calls = fetchMock.mock.calls as [string, RequestInit][];
    const endpointCall = calls.find(([u, i]) =>
      String(u).includes("/accounts/") && String(u).includes("/endpoint") && i?.method === "POST"
    );
    const segCall = calls.find(([u, i]) =>
      String(u).includes("/accounts/") && String(u).includes("/segments") && i?.method === "POST"
    );
    expect(endpointCall).toBeUndefined(); // must NOT have called setEndpoint
    expect(segCall).toBeDefined();        // must have called setComposition
  });
});

it("failed write op surfaces an error message", async () => {
  // Stub: createSegment returns 422 error
  stubFetch((url, init) => {
    const u = String(url);
    if (init?.method === "POST" && u.includes("/segments") && !u.includes("/accounts/")) {
      return { ok: false, status: 422, json: async () => ({ detail: "boom" }) };
    }
    return undefined;
  });

  render(<MemoryRouter><Flow /></MemoryRouter>);
  await screen.findByTestId("echart");

  // Type a label and click 新建人群 button (labeled "+ 加人群")
  fireEvent.change(screen.getByPlaceholderText(/新建人群标签/), { target: { value: "坏数据" } });
  fireEvent.click(screen.getByRole("button", { name: /加人群/ }));

  // The error from the API should surface in the UI
  await waitFor(() => {
    expect(screen.getByText(/boom/)).toBeInTheDocument();
  });
});

it("populates the assignable pool from GET /segments and /endpoints on mount", async () => {
  stubFetch((url, init) => {
    const u = String(url);
    if (u.endsWith("/segments") && init?.method !== "POST") {
      return { ok: true, json: async () => [{ id: 1, label: "crypto" }] };
    }
    if (u.endsWith("/endpoints") && init?.method !== "POST") {
      return { ok: true, json: async () => [{ id: 9, name: "Nina", url_pattern: "linktr.ee/nina" }] };
    }
    return undefined;
  });

  render(<MemoryRouter><Flow /></MemoryRouter>);
  await screen.findByTestId("echart");

  // Select an account so the segment chips + endpoint select render.
  const accountSelect = document.querySelectorAll("select")[0];
  fireEvent.change(accountSelect, { target: { value: "4" } });

  // The 'crypto' segment chip renders WITHOUT the user creating it this session.
  expect(await screen.findByRole("button", { name: "crypto" })).toBeInTheDocument();

  // The 'Nina' endpoint appears as an <option> in the 变现出口 select.
  const ninaOption = await screen.findByRole("option", { name: "Nina" });
  expect(ninaOption).toBeInTheDocument();
});

it("重置为示例 calls POST /demo/reset AND refreshes the displayed pool", async () => {
  // Before reset the pool is empty; once /demo/reset fires, subsequent GETs return
  // the rebuilt server pool. This proves the reset → reload chain actually
  // re-fetches and re-renders the assignable pool (not just that the POST fired).
  let reset = false;
  const fetchMock = stubFetch((url, init) => {
    const u = String(url);
    if (u.includes("/demo/reset")) {
      reset = true;
      return { ok: true, json: async () => ({ endpoints: 1, segments: 1, routed: 0 }) };
    }
    if (u.endsWith("/segments") && init?.method !== "POST") {
      return { ok: true, json: async () => (reset ? [{ id: 1, label: "crypto" }] : []) };
    }
    if (u.endsWith("/endpoints") && init?.method !== "POST") {
      return { ok: true, json: async () => (reset ? [{ id: 9, name: "Nina", url_pattern: "linktr.ee/nina" }] : []) };
    }
    return undefined;
  });

  render(<MemoryRouter><Flow /></MemoryRouter>);
  await screen.findByTestId("echart");

  // Reset buttons appear in the config panel; click the first one.
  fireEvent.click(screen.getAllByRole("button", { name: /重置为示例/ })[0]);

  // The POST fired.
  await waitFor(() => {
    const call = (fetchMock.mock.calls as [string, RequestInit][]).find(
      ([u, i]) => String(u).includes("/demo/reset") && i?.method === "POST",
    );
    expect(call).toBeDefined();
  });

  // Select an account so the segment chips + endpoint select render.
  fireEvent.change(document.querySelectorAll("select")[0], { target: { value: "4" } });

  // Post-reset pool is now displayed: 'crypto' chip + 'Nina' endpoint option.
  expect(await screen.findByRole("button", { name: "crypto" })).toBeInTheDocument();
  expect(await screen.findByRole("option", { name: "Nina" })).toBeInTheDocument();
});
