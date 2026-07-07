import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AccountDetail } from "./AccountDetail";
import type { AccountDetail as AccountDetailT } from "../api/types";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const DETAIL: AccountDetailT = {
  id: 1, platform: "xiaohongshu", handle: "@a1", vertical: "beauty", positioning: "美妆",
  objective_weights: { growth: 0.4, engagement: 0.3, commercial: 0.2, positioning: 0.1 },
  snapshots: [
    { id: 1, ts: "2026-07-01T00:00:00+00:00", followers: 100000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 2, source_tier: "manual" },
    { id: 2, ts: "2026-07-06T00:00:00+00:00", followers: 110000, engagement_rate: 0.05, hit_rate: 0.1, conversions: 3, source_tier: "manual" },
  ],
  content_items: [],
  loop_runs: [
    { id: 8, ts: "2026-07-04T01:00:00+00:00", diagnosis: "首轮基线", verify_result: { improved: false, delta: 0 }, status: "no_progress",
      evaluation: { id: 2, composite_score: 62, breakdown: { growth: 60, engagement: 55, commercial: 40, positioning: 70 }, created_at: "2026-07-04T01:00:00+00:00" },
      recommendations: [], drafts: [] },
    { id: 9, ts: "2026-07-06T01:00:00+00:00", diagnosis: "定位偏散，建议聚焦", verify_result: { improved: true, delta: 12 }, status: "ok",
      evaluation: { id: 3, composite_score: 88, breakdown: { growth: 90, engagement: 85, commercial: 80, positioning: 95 }, created_at: "2026-07-06T01:00:00+00:00" },
      recommendations: [{ id: 5, kind: "positioning", content: "聚焦平价美妆测评", status: "pending" }],
      drafts: [{ id: 7, kind: "topic", content: "5款百元粉底横评", review_status: "pending" }] },
  ],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => DETAIL }));
});
afterEach(() => vi.unstubAllGlobals());

it("renders score, effect curve, goal progress, and review items", async () => {
  render(
    <MemoryRouter initialEntries={["/accounts/1"]}>
      <Routes><Route path="/accounts/:id" element={<AccountDetail />} /></Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("@a1")).toBeInTheDocument();
  expect(screen.getByText("88")).toBeInTheDocument();               // 大号价值分 (latest)
  expect(screen.getByText(/定位偏散/)).toBeInTheDocument();          // 诊断 in timeline
  expect(screen.getByText(/聚焦平价美妆测评/)).toBeInTheDocument();   // 建议
  expect(screen.getByText(/5款百元粉底横评/)).toBeInTheDocument();    // 草稿

  // Loop 见效曲线 (EffectCurve) present
  expect(screen.getByText(/见效曲线/)).toBeInTheDocument();
  // 目标进度 (GoalProgress) present — shows objective weights
  expect(screen.getByText(/目标进度/)).toBeInTheDocument();
  // charts render (trend + radar + effect curve)
  expect(screen.getAllByTestId("echart").length).toBeGreaterThanOrEqual(2);
});

it("adopt button POSTs to /recommendations/5/status with adopted", async () => {
  const ADOPTED_REC = { id: 5, kind: "positioning", content: "聚焦平价美妆测评", status: "adopted" };
  const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && (url as string).includes("/recommendations/5/status")) {
      return Promise.resolve({ ok: true, json: async () => ADOPTED_REC });
    }
    return Promise.resolve({ ok: true, json: async () => DETAIL });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter initialEntries={["/accounts/1"]}>
      <Routes><Route path="/accounts/:id" element={<AccountDetail />} /></Routes>
    </MemoryRouter>,
  );

  // Wait for page to load
  await screen.findByText("@a1");

  // Click the 采纳 button for the recommendation (first one; second is for the draft)
  fireEvent.click(screen.getAllByText("采纳")[0]);

  await waitFor(() => {
    const postCall = fetchMock.mock.calls.find(
      (args: unknown[]) => {
        const [url, init] = args as [string, RequestInit];
        return url === "http://localhost:8000/recommendations/5/status" && init?.method === "POST";
      },
    );
    expect(postCall).toBeDefined();
    const [, init] = postCall as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ status: "adopted" });
  });
});
