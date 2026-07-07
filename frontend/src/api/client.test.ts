import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./client";

describe("api client", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("GET /accounts hits the base url", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);
    await api.listAccounts();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/accounts", expect.any(Object));
  });

  it("POST setRecommendationStatus sends body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1, kind: "positioning", content: "x", status: "adopted" }) });
    vi.stubGlobal("fetch", fetchMock);
    const out = await api.setRecommendationStatus(1, "adopted");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/recommendations/1/status",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ status: "adopted" }) }),
    );
    expect(out.status).toBe("adopted");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: "nope" }) }));
    await expect(api.getAccount(999)).rejects.toThrow();
  });
});
