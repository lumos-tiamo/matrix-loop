import { it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AccountDetail } from "./AccountDetail";
import type { AccountDetail as AccountDetailT } from "../api/types";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const DETAIL: AccountDetailT = {
  id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: "美妆",
  objective_weights: { growth: 1, engagement: 0, commercial: 0, positioning: 0 },
  snapshots: [
    { id: 1, ts: "2026-07-01T00:00:00+00:00", followers: 100000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 2, source_tier: "manual" },
    { id: 2, ts: "2026-07-06T00:00:00+00:00", followers: 110000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 3, source_tier: "manual" },
  ],
  content_items: [],
  loop_runs: [
    { id: 9, ts: "2026-07-06T01:00:00+00:00", diagnosis: "定位偏散，建议聚焦", verify_result: { improved: true, delta: 12 }, status: "ok",
      evaluation: { id: 3, composite_score: 88, breakdown: { growth: 90, engagement: 85, commercial: 80, positioning: 95 }, created_at: "2026-07-06T01:00:00+00:00" },
      recommendations: [{ id: 5, kind: "positioning", content: "聚焦平价美妆测评", status: "pending" }],
      drafts: [{ id: 7, kind: "topic", content: "5款百元粉底横评", review_status: "pending" }] },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => DETAIL }));
});

it("renders score, diagnosis, and review items", async () => {
  render(
    <MemoryRouter initialEntries={["/accounts/1"]}>
      <Routes><Route path="/accounts/:id" element={<AccountDetail />} /></Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("@a1")).toBeInTheDocument();
  expect(screen.getByText("88")).toBeInTheDocument();               // 价值分
  expect(screen.getByText(/定位偏散/)).toBeInTheDocument();          // 诊断
  expect(screen.getByText(/聚焦平价美妆测评/)).toBeInTheDocument();   // 建议
  expect(screen.getByText(/5款百元粉底横评/)).toBeInTheDocument();    // 草稿
  expect(screen.getAllByTestId("echart").length).toBeGreaterThanOrEqual(1);
});
