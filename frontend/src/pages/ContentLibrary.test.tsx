import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ContentLibrary } from "./ContentLibrary";
import type { ContentLibraryItem } from "../api/types";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="echart" /> }));

const ITEMS: ContentLibraryItem[] = [
  { id: 1, account_id: 2, account_handle: "@a2", platform: "twitter", topic: "macro trends", views: 8000, likes: 600, comments: 30, published_at: "2026-07-05T00:00:00+00:00" },
  { id: 2, account_id: 1, account_handle: "@a1", platform: "xiaohongshu", topic: "beauty haul", views: 5000, likes: 400, comments: 20, published_at: "2026-07-04T00:00:00+00:00" },
  { id: 3, account_id: 1, account_handle: "@a1", platform: "xiaohongshu", topic: "skincare 101", views: 1200, likes: 90, comments: 5, published_at: "2026-07-03T00:00:00+00:00" },
];

function stubFetch(impl?: (url: string, init?: RequestInit) => unknown) {
  const fn = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (impl) {
      const custom = impl(url, init);
      if (custom !== undefined) return Promise.resolve(custom);
    }
    // /content?platform=xiaohongshu → filter server-side like the real API
    const u = String(url);
    if (u.includes("platform=xiaohongshu")) {
      return Promise.resolve({ ok: true, json: async () => ITEMS.filter((i) => i.platform === "xiaohongshu") });
    }
    return Promise.resolve({ ok: true, json: async () => ITEMS });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => { stubFetch(); });
afterEach(() => vi.unstubAllGlobals());

it("renders content items sorted by views desc (爆文置顶)", async () => {
  render(<MemoryRouter><ContentLibrary /></MemoryRouter>);
  const topics = await screen.findAllByTestId("content-topic");
  expect(topics.map((t) => t.textContent)).toEqual(["macro trends", "beauty haul", "skincare 101"]);
});

it("filters by platform chip", async () => {
  const fetchMock = stubFetch();
  render(<MemoryRouter><ContentLibrary /></MemoryRouter>);
  await screen.findByText("macro trends");
  fireEvent.click(screen.getByRole("button", { name: "小红书" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find((args: unknown[]) =>
      String((args as [string])[0]).includes("platform=xiaohongshu"),
    );
    expect(call).toBeDefined();
  });
  await waitFor(() => {
    expect(screen.queryByText("macro trends")).not.toBeInTheDocument();
    expect(screen.getByText("beauty haul")).toBeInTheDocument();
  });
});
