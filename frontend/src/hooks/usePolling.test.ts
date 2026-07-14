// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { usePolling } from "./usePolling";

describe("usePolling", () => {
  it("calls fn immediately then on interval", async () => {
    vi.useFakeTimers();
    const fn = vi.fn().mockResolvedValue(1);
    renderHook(() => usePolling(fn, 3000));
    expect(fn).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
