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
