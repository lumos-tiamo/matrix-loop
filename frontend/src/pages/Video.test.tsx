import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Video } from "./Video";

const ACCOUNTS = [
  { id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null,
    latest_followers: 1000, latest_composite_score: 60, latest_loop_status: "ok", source_tier: "api" },
];
const USAGE = {
  today_count: 7, today_cost: 3.5, total_count: 12, total_cost: 11.5,
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
  await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());   // today_count
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
  target_seconds: 90,
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
  fireEvent.change(select, { target: { value: "4" } });
  // brief main_direction shows up in the editor input
  await waitFor(() => {
    const input = screen.getByDisplayValue("web3");
    expect(input).toBeInTheDocument();
  });
  expect(screen.getByDisplayValue("Nina")).toBeInTheDocument();
});

it("brief editor shows the target-seconds field from the loaded brief", async () => {
  stub((url) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: true, json: async () => BRIEF };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => ({ id: 4, platform: "youtube", handle: "@nina", vertical: "crypto", positioning: null, objective_weights: {}, snapshots: [], content_items: [], loop_runs: [] }) };
    return undefined;
  });
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  await waitFor(() => {
    const input = screen.getByLabelText(/视频时长/) as HTMLInputElement;
    expect(input.value).toBe("90");
  });
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
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  const mainInput = await screen.findByPlaceholderText(/主方向/);
  fireEvent.change(mainInput, { target: { value: "web3" } });
  fireEvent.click(screen.getByRole("button", { name: /保存定调/ }));
  await waitFor(() => expect(posted.length).toBe(1));
});

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
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  // adopted topic -> 生成脚本 button present
  fireEvent.click(await screen.findByRole("button", { name: /生成脚本/ }));
  await waitFor(() => expect(calls).toContain("gen-script"));
});

it("a topic/script draft card expands to show full content", async () => {
  const LONG = "A".repeat(220) + " HOOKLINE_HIDDEN_TAIL " + "B".repeat(50);
  stub((url) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [] };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([{ id: 1, kind: "script", content: LONG, review_status: "pending" }]) };
    return undefined;
  });
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  // preview shown (200-char slice), full tail hidden
  const toggle = await screen.findByRole("button", { name: /展开全文/ });
  expect(screen.queryByText(/HOOKLINE_HIDDEN_TAIL/)).not.toBeInTheDocument();
  // expand -> full content present
  fireEvent.click(toggle);
  await waitFor(() => expect(screen.getByText(/HOOKLINE_HIDDEN_TAIL/)).toBeInTheDocument());
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
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  fireEvent.click(await screen.findByRole("button", { name: /生成视频/ }));
  await waitFor(() => expect(calls).toContain("gen-video"));
});

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
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  // asset row shows provider + a link to the media
  expect(await screen.findByText(/fake/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /通过/ }));
  await waitFor(() => expect(calls.length).toBe(1));
  expect(calls[0].body).toContain("approved");
});

it("publishes an approved asset via 发布", async () => {
  const calls: string[] = [];
  const approved = { ...ASSET, review_status: "approved" };
  stub((url, init) => {
    if (url.endsWith("/accounts")) return { ok: true, json: async () => ACCOUNTS };
    if (url.endsWith("/video/usage")) return { ok: true, json: async () => USAGE };
    if (url.match(/\/accounts\/4\/brief$/)) return { ok: false, status: 404, json: async () => ({}) };
    if (url.match(/\/accounts\/4$/)) return { ok: true, json: async () => detailWithDrafts([]) };
    if (url.match(/\/accounts\/4\/publish$/) && init?.method === "POST") {
      calls.push("publish");
      return { ok: true, json: async () => ({ id: 1, account_id: 4, video_asset_id: 9, aitoearn_flow_id: "f1", aitoearn_task_id: "t1", platform_work_id: null, status: "queued", publish_at: null, media_urls: [], caption: "x", created_at: "2026-07-09T00:00:00Z" }) };
    }
    if (url.includes("/publish/dispatches")) return { ok: true, json: async () => [] };
    if (url.includes("/video-assets")) return { ok: true, json: async () => [approved] };
    return undefined;
  });
  render(<MemoryRouter initialEntries={["/video"]}><Video /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText(/选择账号/), { target: { value: "4" } });
  fireEvent.click(await screen.findByRole("button", { name: /发布/ }));
  await waitFor(() => expect(calls).toContain("publish"));
});
