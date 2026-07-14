import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StepTracker, segState } from "./StepTracker";

describe("StepTracker", () => {
  it("maps step index to done/active/upcoming", () => {
    expect(segState(0, 4, "running")).toBe("done");
    expect(segState(4, 4, "running")).toBe("active");
    expect(segState(6, 4, "running")).toBe("upcoming");
    expect(segState(5, 5, "blocked")).toBe("warn");
  });
  it("renders 8 steps", () => {
    const { container } = render(<StepTracker stepIndex={4} status="running" />);
    expect(container.querySelectorAll("[data-step]").length).toBe(8);
  });
});
