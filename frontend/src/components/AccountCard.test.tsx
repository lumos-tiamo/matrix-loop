import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AccountCard } from "./AccountCard";
import type { FlywheelAccountLive } from "../api/types";

const base: FlywheelAccountLive = {
  account_id: 1, platform: "tiktok", handle: "@nina_web3", autopilot: true,
  status: "running", current_step: "video", step_index: 4, steps_done: 4,
  elapsed_sec: 102, blocked_reason: null,
  last_event: { step: "script", status: "ok", detail: null, ts: new Date().toISOString() },
  kpis: { followers: 12400, followers_delta: 2.1, views_7d: 86200, score: 78 },
  cost_cycle: 0.42, next_run_eta_sec: null, synced_at: new Date().toISOString(),
};

describe("AccountCard", () => {
  it("running shows handle, cost, platform", () => {
    render(<AccountCard a={base} />);
    expect(screen.getByText("@nina_web3")).toBeTruthy();
    expect(screen.getByText(/\$0.42/)).toBeTruthy();
    expect(screen.getByText(/TikTok/i)).toBeTruthy();
  });
  it("blocked shows action banner + reason", () => {
    render(<AccountCard a={{ ...base, status: "blocked", current_step: "approve", step_index: 5, blocked_reason: "待人工审核" }} />);
    expect(screen.getByText(/待人工审核/)).toBeTruthy();
  });
  it("ok shows next-run countdown", () => {
    render(<AccountCard a={{ ...base, status: "ok", next_run_eta_sec: 724 }} />);
    expect(screen.getByText(/下一轮/)).toBeTruthy();
  });
});
