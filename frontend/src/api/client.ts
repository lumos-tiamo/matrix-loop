import type {
  AccountListItem, AccountDetail, LoopRunOut, RecommendationOut, DraftOut,
  Overview, ContentLibraryItem,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string) ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.status.toString();
    try { detail = (await res.json())?.detail ?? detail; } catch { /* ignore */ }
    throw new Error(`API ${path} failed: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listAccounts: () => req<AccountListItem[]>("/accounts"),
  getAccount: (id: number) => req<AccountDetail>(`/accounts/${id}`),
  getOverview: () => req<Overview>("/overview"),
  getContent: (params?: { platform?: string; account_id?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.platform) qs.set("platform", params.platform);
    if (params?.account_id != null) qs.set("account_id", String(params.account_id));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return req<ContentLibraryItem[]>(`/content${q ? `?${q}` : ""}`);
  },
  batchRun: (sync = true) =>
    req<Record<string, unknown>>(`/batch/run?sync=${sync}`, { method: "POST" }),
  triggerLoop: (id: number) => req<LoopRunOut>(`/accounts/${id}/loop`, { method: "POST" }),
  setRecommendationStatus: (id: number, status: string) =>
    req<RecommendationOut>(`/recommendations/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  setDraftStatus: (id: number, review_status: string) =>
    req<DraftOut>(`/drafts/${id}/status`, { method: "POST", body: JSON.stringify({ review_status }) }),
};
