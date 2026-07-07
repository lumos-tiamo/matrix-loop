import type { AccountListItem, AccountDetail, LoopRunOut, RecommendationOut, DraftOut } from "./types";

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
  triggerLoop: (id: number) => req<LoopRunOut>(`/accounts/${id}/loop`, { method: "POST" }),
  setRecommendationStatus: (id: number, status: string) =>
    req<RecommendationOut>(`/recommendations/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  setDraftStatus: (id: number, review_status: string) =>
    req<DraftOut>(`/drafts/${id}/status`, { method: "POST", body: JSON.stringify({ review_status }) }),
};
