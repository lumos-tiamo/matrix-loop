import type {
  AccountListItem, AccountDetail, LoopRunOut, RecommendationOut, DraftOut,
  Overview, ContentLibraryItem,
  FlowData, SegmentOut, EndpointOut, CompositionItem,
  ChannelBriefOut, VideoAssetOut, VideoUsage, SetBriefIn,
  PublishDispatchOut,
  PublishPlanOut, PublishPlanIn,
  FlywheelState,
  FlywheelAccountLive, FlywheelEventLive,
  ScheduleItem, TrendItem, CarouselItem, DayItem,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string) ?? "http://localhost:8000";

export const API_BASE = BASE;

/** Resolve a playable media URL. Backend serves files at `{API}/media/...` but older
 *  assets baked a wrong host (e.g. :8010) into media_url — rewrite any `/media/...` to our
 *  API origin so playback works for both old and new assets. External URLs pass through. */
export function mediaSrc(url?: string | null): string | null {
  if (!url) return null;
  const i = url.indexOf("/media/");
  if (i >= 0) return `${BASE}${url.slice(i)}`;
  if (/^https?:\/\//.test(url)) return url;
  return `${BASE}${url.startsWith("/") ? "" : "/"}${url}`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.status.toString();
    try { detail = (await res.json())?.detail ?? detail; } catch { /* ignore */ }
    const err = new Error(`API ${path} failed: ${detail}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
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
  batchRun: (sync = true, opts?: { maxAccounts?: number; background?: boolean }) => {
    const qs = new URLSearchParams({ sync: String(sync) });
    if (opts?.maxAccounts != null) qs.set("max_accounts", String(opts.maxAccounts));
    if (opts?.background) qs.set("background", "true");
    return req<{ run_id?: string; status?: string } & Record<string, unknown>>(
      `/batch/run?${qs.toString()}`, { method: "POST" });
  },
  getBatchRun: (runId: string) =>
    req<{ run_id: string; status: string; report: Record<string, unknown> | null; error: string | null }>(
      `/batch/runs/${runId}`),
  importSnapshots: (csv: string) =>
    req<Record<string, unknown>>("/import/snapshots", { method: "POST", body: JSON.stringify({ csv }) }),
  syncAccount: (id: number) =>
    req<Record<string, unknown>>(`/accounts/${id}/sync`, { method: "POST" }),
  triggerLoop: (id: number) => req<LoopRunOut>(`/accounts/${id}/loop`, { method: "POST" }),
  setRecommendationStatus: (id: number, status: string) =>
    req<RecommendationOut>(`/recommendations/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  setDraftStatus: (id: number, review_status: string) =>
    req<DraftOut>(`/drafts/${id}/status`, { method: "POST", body: JSON.stringify({ review_status }) }),

  // ---- Flow / 导流 ----
  getFlow: () => req<FlowData>("/flow"),
  listSegments: () => req<SegmentOut[]>("/segments"),
  listEndpoints: () => req<EndpointOut[]>("/endpoints"),
  resetDemo: () => req<{ endpoints: number; segments: number; routed: number }>(
    "/demo/reset", { method: "POST" }),
  createSegment: (label: string) =>
    req<SegmentOut>("/segments", { method: "POST", body: JSON.stringify({ label }) }),
  createEndpoint: (name: string, url_pattern?: string) =>
    req<EndpointOut>("/endpoints", {
      method: "POST",
      body: JSON.stringify({ name, url_pattern: url_pattern ?? null }),
    }),
  setComposition: (accountId: number, segments: CompositionItem[]) =>
    req<Record<string, unknown>>(`/accounts/${accountId}/segments`, {
      method: "POST",
      body: JSON.stringify({ segments }),
    }),
  setEndpoint: (accountId: number, endpointId: number | null) =>
    req<Record<string, unknown>>(`/accounts/${accountId}/endpoint`, {
      method: "POST",
      body: JSON.stringify({ endpoint_id: endpointId }),
    }),
  classifyAudience: (accountId: number) =>
    req<{ account_id: number; segments: string[] }>(`/accounts/${accountId}/classify-audience`, {
      method: "POST",
    }),

  // ---- Video workbench ----
  getBrief: (accountId: number) => req<ChannelBriefOut>(`/accounts/${accountId}/brief`),
  setBrief: (accountId: number, body: SetBriefIn) =>
    req<{ account_id: number; id: number }>(`/accounts/${accountId}/brief`, {
      method: "POST", body: JSON.stringify(body),
    }),
  generateScript: (draftId: number) =>
    req<DraftOut>(`/drafts/${draftId}/generate-script`, { method: "POST" }),
  generateVideo: (accountId: number, scriptDraftId: number) =>
    req<VideoAssetOut>(`/accounts/${accountId}/generate-video`, {
      method: "POST", body: JSON.stringify({ script_draft_id: scriptDraftId }),
    }),
  listVideoAssets: (params?: { account_id?: number; review_status?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.account_id != null) qs.set("account_id", String(params.account_id));
    if (params?.review_status) qs.set("review_status", params.review_status);
    if (params?.status) qs.set("status", params.status);
    const q = qs.toString();
    return req<VideoAssetOut[]>(`/video-assets${q ? `?${q}` : ""}`);
  },
  setVideoReview: (id: number, review_status: string) =>
    req<VideoAssetOut>(`/video-assets/${id}/status`, {
      method: "POST", body: JSON.stringify({ review_status }),
    }),
  queuePalmier: (id: number) =>
    req<VideoAssetOut>(`/video-assets/${id}/queue-palmier`, { method: "POST" }),
  regenerateVideo: (id: number) =>
    req<VideoAssetOut>(`/video-assets/${id}/regenerate`, { method: "POST" }),
  getVideoUsage: () => req<VideoUsage>("/video/usage"),
  publish: (accountId: number, videoAssetId: number, caption?: string) =>
    req<PublishDispatchOut>(`/accounts/${accountId}/publish`, {
      method: "POST", body: JSON.stringify({ video_asset_id: videoAssetId, caption: caption ?? null }),
    }),
  listDispatches: (accountId: number) =>
    req<PublishDispatchOut[]>(`/publish/dispatches?account_id=${accountId}`),
  refreshDispatch: (id: number) => req<PublishDispatchOut>(`/publish/dispatches/${id}`),
  // ---- Publish plan (step-6 companion content) ----
  getPublishPlan: (assetId: number) => req<PublishPlanOut>(`/video-assets/${assetId}/publish-plan`),
  putPublishPlan: (assetId: number, body: PublishPlanIn) =>
    req<PublishPlanOut>(`/video-assets/${assetId}/publish-plan`, {
      method: "PUT", body: JSON.stringify(body),
    }),

  // ---- Schedule / 排期日历(每日16条) ----
  getSchedule: () => req<ScheduleItem[]>("/schedule"),
  getDayPlan: () => req<DayItem[]>("/day-plan"),
  rescheduleAsset: (id: number, posting_time: string) =>
    req<{ asset_id: number; posting_time: string }>(`/video-assets/${id}/reschedule`, {
      method: "PUT", body: JSON.stringify({ posting_time }),
    }),
  generateDaily: (rounds = 4) =>
    req<{ started: boolean; rounds: number; from_trends: boolean }>(
      `/schedule/generate-daily?rounds=${rounds}`, { method: "POST" }),
  runFullDaily: (rounds = 4) =>
    req<{ started: boolean; rounds: number; steps: string[] }>(
      `/schedule/run-full-daily?rounds=${rounds}`, { method: "POST" }),
  getTrends: (niche?: string) =>
    req<TrendItem[]>(`/trends${niche ? `?niche=${encodeURIComponent(niche)}` : ""}`),
  // ---- 图文 carousels ----
  getCarousels: () => req<CarouselItem[]>("/carousels"),
  generateCarousels: (accountId?: number) =>
    req<{ started: boolean; account_id: number | null }>(
      `/carousel/generate-daily${accountId ? `?account_id=${accountId}` : ""}`, { method: "POST" }),

  // ---- Flywheel ----
  getFlywheel: () => req<FlywheelState>("/flywheel"),
  flywheelStatus: () => req<{ paused: boolean }>("/flywheel/status"),
  pauseFlywheel: () => req<{ paused: boolean }>("/flywheel/pause", { method: "POST" }),
  resumeFlywheel: () => req<{ paused: boolean }>("/flywheel/resume", { method: "POST" }),
  setAutopilot: (accountId: number, enabled: boolean) =>
    req<{ account_id: number; autopilot: boolean }>(`/accounts/${accountId}/autopilot`, {
      method: "POST", body: JSON.stringify({ enabled }),
    }),
  getFlywheelAccounts: () => req<FlywheelAccountLive[]>("/flywheel/accounts"),
  getFlywheelEvents: (sinceId?: number) =>
    req<FlywheelEventLive[]>(`/flywheel/events${sinceId ? `?since_id=${sinceId}` : ""}`),
};
