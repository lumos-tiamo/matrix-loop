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
  snapshots: SnapshotOut[]; content_items: ContentItemOut[]; loop_runs: LoopRunOut[];
}
