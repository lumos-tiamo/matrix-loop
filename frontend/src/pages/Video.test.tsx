import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Video } from "./Video";

const ACCOUNTS = [
  { id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null,
    latest_followers: 1000, latest_composite_score: 60, latest_loop_status: "ok", source_tier: "api" },
];
const USAGE = {
  today_count: 3, today_cost: 3.5, total_count: 12, total_cost: 11.5,
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
