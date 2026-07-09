export interface AccountListItem {
  id: number;
  platform: string;
  handle: string;
  vertical: string | null;
  positioning: string | null;
  latest_followers: number | null;
  latest_composite_score: number | null;
  latest_loop_status: string | null;
  source_tier: string | null;
}

export interface SnapshotOut {
  id: number; ts: string; followers: number | null; engagement_rate: number | null;
  hit_rate: number | null; conversions: number | null; source_tier: string;
}
export interface ContentItemOut { id: number; topic: string | null; views: number | null; likes: number | null; }
export interface RecommendationOut { id: number; kind: string; content: string; status: string; }
export interface DraftOut { id: number; kind: string; content: string; review_status: string; }
export interface EvaluationOut { id: number; composite_score: number; breakdown: Record<string, number>; created_at: string; }
export interface LoopRunOut {
  id: number; ts: string; diagnosis: string | null; verify_result: Record<string, unknown>; status: string;
  evaluation: EvaluationOut | null; recommendations: RecommendationOut[]; drafts: DraftOut[];
}
export interface AccountDetail {
  id: number; platform: string; handle: string; vertical: string | null; positioning: string | null;
  objective_weights: Record<string, number> | null;
  acceptance_criteria?: string | null;
  snapshots: SnapshotOut[]; content_items: ContentItemOut[]; loop_runs: LoopRunOut[];
}

// ---- Overview (GET /overview) ----
export interface OverviewKpis {
  total_accounts: number;
  avg_score: number;
  needs_attention: number;
  platforms: number;
  pending_review: number;
}
export interface PlatformHealth {
  platform: string;
  growth: number;
  engagement: number;
  commercial: number;
  positioning: number;
}
export interface TrendPoint {
  date: string;
  followers: number;
  engagement: number;
}
export interface OverviewAlert {
  account_id: number;
  handle: string;
  platform: string;
  kind: string;
  detail: string;
}
export interface TopMover {
  account_id: number;
  handle: string;
  platform: string;
  delta_followers: number;
}
export interface PositioningDistribution {
  clear: number;
  ok: number;
  scattered: number;
}
export interface Overview {
  kpis: OverviewKpis;
  platform_health: PlatformHealth[];
  trend: TrendPoint[];
  alerts: OverviewAlert[];
  top_movers: TopMover[];
  positioning_distribution: PositioningDistribution;
}

// ---- Flow / Sankey (GET /flow) ----
export interface FlowNode {
  name: string;
}
export interface FlowLink {
  source: string;
  target: string;
  value: number;
}
export interface FlowData {
  nodes: FlowNode[];
  links: FlowLink[];
}

export interface SegmentOut {
  id: number;
  label: string;
}
export interface EndpointOut {
  id: number;
  name: string;
  url_pattern: string | null;
}
export interface CompositionItem {
  segment_id: number;
  weight: number;
}

// ---- Content library (GET /content) ----
export interface ContentLibraryItem {
  id: number;
  account_id: number;
  account_handle: string;
  platform: string;
  topic: string | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  published_at: string | null;
}

// ---- Video workbench ----
export interface ChannelBriefOut {
  account_id: number;
  id: number;
  main_direction: string;
  sub_niches: string[];
  tone: string | null;
  language: string;
  persona: string | null;
  format: string;
  compliance_stance: string;
}

export interface VideoAssetOut {
  id: number;
  account_id: number;
  script_draft_id: number | null;
  provider: string;
  media_url: string | null;
  duration: number | null;
  cost: number;
  status: string;
  review_status: string;
  created_at: string;
}

export interface VideoUsage {
  today_count: number;
  today_cost: number;
  total_count: number;
  total_cost: number;
  caps: {
    max_videos_per_day: number;
    per_account_per_day: number;
    per_channel_per_day: number;
    video_budget: number;
  };
}

export interface SetBriefIn {
  main_direction: string;
  sub_niches: string[];
  tone?: string | null;
  language?: string;
  persona?: string | null;
  format?: string;
  compliance_stance?: string;
}

export interface PublishDispatchOut {
  id: number;
  account_id: number;
  video_asset_id: number | null;
  aitoearn_flow_id: string | null;
  aitoearn_task_id: string | null;
  platform_work_id: string | null;
  status: string;
  publish_at: string | null;
  media_urls: string[];
  caption: string | null;
  created_at: string;
}
