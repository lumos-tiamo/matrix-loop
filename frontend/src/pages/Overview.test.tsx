import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Overview } from "./Overview";
import type { AccountListItem } from "../api/types";

const ACCOUNTS: AccountListItem[] = [
  { id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: null, latest_followers: 88000, latest_composite_score: 88, latest_loop_status: "ok", source_tier: "manual" },
  { id: 2, platform: "tiktok", handle: "@a2", vertical: null, positioning: null, latest_followers: 45000, latest_composite_score: 63, latest_loop_status: "no_progress", source_tier: "scrape" },
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ACCOUNTS }));
});
afterEach(() => vi.unstubAllGlobals());

it("renders stat tiles and both accounts in the table", async () => {
  render(<MemoryRouter><Overview /></MemoryRouter>);
  expect(await screen.findByText("@a1")).toBeInTheDocument();
  expect(screen.getByText("@a2")).toBeInTheDocument();
  // 需介入队列出现 no_progress 的 @a2（用队列专属文案唯一定位）
  expect(screen.getByText(/需介入 \(连续无进展\)/)).toBeInTheDocument();
});
