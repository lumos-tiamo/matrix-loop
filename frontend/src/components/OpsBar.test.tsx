import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { OpsBar } from "./OpsBar";
import type { AccountListItem } from "../api/types";

const ACCOUNTS: AccountListItem[] = [
  {
    id: 1,
    platform: "xiaohongshu",
    handle: "@test1",
    vertical: "beauty",
    positioning: null,
    latest_followers: 10000,
    latest_composite_score: 70,
    latest_loop_status: "ok",
    source_tier: "manual",
  },
];

function stubFetch(impl?: (url: string, init?: RequestInit) => unknown) {
  const fn = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (impl) {
      const custom = impl(url, init);
      if (custom !== undefined) return Promise.resolve(custom);
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => { stubFetch(); });
afterEach(() => vi.unstubAllGlobals());

it("renders the three action buttons", () => {
  render(<OpsBar accounts={ACCOUNTS} />);
  expect(screen.getByRole("button", { name: /跑一批/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /导入 CSV/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /同步/ })).toBeInTheDocument();
});

it("clicking 跑一批 calls POST /batch/run", async () => {
  const fetchMock = stubFetch((url, init) => {
    if (init?.method === "POST" && String(url).includes("/batch/run")) {
      return { ok: true, json: async () => ({ total: 1 }) };
    }
    return undefined;
  });
  const onDone = vi.fn();
  render(<OpsBar accounts={ACCOUNTS} onDone={onDone} />);
  fireEvent.click(screen.getByRole("button", { name: /跑一批/ }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find((args: unknown[]) => {
      const [url, init] = args as [string, RequestInit];
      return String(url).includes("/batch/run") && init?.method === "POST";
    });
    expect(call).toBeDefined();
  });
});

it("clicking 导入 CSV opens the import modal", async () => {
  render(<OpsBar accounts={ACCOUNTS} />);
  fireEvent.click(screen.getByRole("button", { name: /导入 CSV/ }));
  expect(await screen.findByText(/导入快照 CSV/)).toBeInTheDocument();
});

it("✕ button in the import modal is disabled while busy", async () => {
  // Stub fetch to hang so busy stays set during the import
  let resolveFetch!: (v: unknown) => void;
  const hangingFetch = new Promise((r) => { resolveFetch = r; });
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(hangingFetch));

  render(<OpsBar accounts={ACCOUNTS} />);
  fireEvent.click(screen.getByRole("button", { name: /导入 CSV/ }));
  // Fill in some CSV so doImport proceeds past the empty-check
  fireEvent.change(screen.getByPlaceholderText(/platform,handle/), {
    target: { value: "xiaohongshu,@test1,2026-07-07,10000,0.05" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^导入$/ }));

  // While fetch is hanging the ✕ button must be disabled
  const closeBtn = screen.getByRole("button", { name: "✕" });
  expect(closeBtn).toBeDisabled();

  // Resolve the fetch to avoid hanging test
  resolveFetch({ ok: true, json: async () => ({ imported: 1 }) });
});
