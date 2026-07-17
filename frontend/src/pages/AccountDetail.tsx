import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { TrendPoint } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { TrendCard } from "../components/TrendCard";
import { ScoreRadar } from "../components/ScoreRadar";
import { EffectCurve } from "../components/EffectCurve";
import { GoalProgress } from "../components/GoalProgress";
import { LoopTimeline } from "../components/LoopTimeline";
import { ReviewPanel } from "../components/ReviewPanel";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

function scoreColor(score: number): string {
  if (score >= 70) return "#B6FF3C";
  if (score >= 50) return "#4CD4F0";
  return "#FFB020";
}

function fmtFollowers(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 10000) return `${(n / 10000).toFixed(1)}W`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

export function AccountDetail() {
  const { id } = useParams();
  const accountId = Number(id);
  const { data, loading, error, reload } = useAsync(() => api.getAccount(accountId), [accountId]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "loop" | "sync">(null);

  // account-level trend for the multi-metric TrendCard (followers + engagement)
  const trend: TrendPoint[] = useMemo(() => {
    if (!data) return [];
    return [...data.snapshots]
      .sort((a, b) => a.ts.localeCompare(b.ts))
      .map((s) => ({
        date: s.ts.slice(0, 10),
        followers: s.followers ?? 0,
        engagement: s.engagement_rate ?? 0,
      }));
  }, [data]);

  if (loading) return <div className="font-mono text-muted">加载中…</div>;
  if (error || !data) return <div className="font-mono text-alert">加载失败：{error}</div>;

  const latestSnap = [...data.snapshots].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const latestRun = [...data.loop_runs].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const score = latestRun?.evaluation?.composite_score ?? null;
  const color = score != null ? scoreColor(score) : "#8A93A8";

  const runLoop = async () => {
    setActionError(null);
    setBusy("loop");
    try { await api.triggerLoop(accountId); reload(); }
    catch (e) { setActionError(String(e)); }
    finally { setBusy(null); }
  };

  const syncAccount = async () => {
    setActionError(null);
    setBusy("sync");
    try { await api.syncAccount(accountId); reload(); }
    catch (e) {
      const msg = String(e);
      setActionError(/无自动连接器|CSV/.test(msg) ? "该平台无自动连接器，请用「导入 CSV」" : msg);
    }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-[14px]">
      {/* HEADER */}
      <ChartCard className="rise" glow={score != null && score >= 70}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              className="flex h-[68px] w-[68px] items-center justify-center rounded-full"
              style={{ background: `conic-gradient(${color} ${score ?? 0}%, #232B3C 0)` }}
            >
              <span
                className="flex h-[54px] w-[54px] items-center justify-center rounded-full bg-panel font-display text-2xl font-extrabold tabnums"
                style={{ color }}
              >
                {score != null ? score.toFixed(0) : "—"}
              </span>
            </div>
            <div>
              <div className="font-mono text-[11px] uppercase text-muted">
                {PLATFORM_LABEL[data.platform] ?? data.platform}
                {data.vertical ? ` · ${data.vertical}` : ""}
              </div>
              <h1 className="font-display text-2xl font-extrabold">{data.handle}</h1>
              {data.positioning && (
                <div className="mt-[2px] font-mono text-[11px] text-muted">定位：{data.positioning}</div>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2">
              <button
                onClick={runLoop}
                disabled={busy !== null}
                className="rounded-[9px] border-none bg-lime px-[14px] py-2 font-display text-[13px] font-bold text-[#0A0D12] shadow-[0_4px_18px_rgba(182,255,60,0.25)] disabled:opacity-60"
              >
                {busy === "loop" ? "⏳ 运行中…" : "⚡ 跑一轮 Loop"}
              </button>
              <button
                onClick={syncAccount}
                disabled={busy !== null}
                className="rounded-[9px] border border-cyan/50 bg-cyan/[.08] px-3 py-2 font-mono text-xs text-cyan disabled:opacity-50"
              >
                {busy === "sync" ? "⏳ 同步中…" : "🔌 同步"}
              </button>
            </div>
            {actionError && <p className="max-w-[280px] text-right font-mono text-[11px] text-alert">{actionError}</p>}
          </div>
        </div>
      </ChartCard>

      {/* KPI ROW */}
      <div className="grid grid-cols-2 gap-[14px] md:grid-cols-4">
        <Kpi label="粉丝" value={fmtFollowers(latestSnap?.followers)} tone="text-lime" delay={0} />
        <Kpi label="互动率" value={latestSnap?.engagement_rate != null ? `${(latestSnap.engagement_rate * 100).toFixed(1)}%` : "—"} tone="text-cyan" delay={60} />
        <Kpi label="爆文率" value={latestSnap?.hit_rate != null ? `${(latestSnap.hit_rate * 100).toFixed(0)}%` : "—"} tone="text-violet" delay={120} />
        <Kpi label="转化" value={String(latestSnap?.conversions ?? "—")} tone="text-pink" delay={180} />
      </div>

      {/* MULTI-METRIC TREND + EVAL RADAR */}
      <div className="grid gap-[14px] lg:grid-cols-[1.35fr_1fr]">
        <TrendCard trend={trend} style={{ animationDelay: "120ms" }} />
        <ChartCard title={<>🕸 评估拆解</>} className="rise" style={{ animationDelay: "180ms" }}>
          {latestRun?.evaluation ? <ScoreRadar breakdown={latestRun.evaluation.breakdown} /> : <Empty />}
        </ChartCard>
      </div>

      {/* EFFECT CURVE + GOAL PROGRESS */}
      <div className="grid gap-[14px] lg:grid-cols-2">
        <EffectCurve runs={data.loop_runs} style={{ animationDelay: "160ms" }} />
        <GoalProgress
          weights={data.objective_weights}
          breakdown={latestRun?.evaluation?.breakdown ?? null}
          acceptanceCriteria={data.acceptance_criteria}
          style={{ animationDelay: "220ms" }}
        />
      </div>

      {/* LOOP HISTORY + REVIEW */}
      <div className="grid gap-[14px] lg:grid-cols-2">
        <ChartCard title={<>🧭 Loop 历史</>} className="rise" style={{ animationDelay: "200ms" }}>
          {data.loop_runs.length ? <LoopTimeline runs={data.loop_runs} /> : <Empty />}
        </ChartCard>
        <ChartCard title={<>📝 本轮待审产出</>} className="rise" style={{ animationDelay: "260ms" }}>
          {latestRun ? <ReviewPanel run={latestRun} onChange={reload} /> : <Empty />}
        </ChartCard>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone, delay }: { label: string; value: string; tone: string; delay: number }) {
  return (
    <div
      className="glass px-4 py-3 rise"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-[6px] font-display text-2xl font-extrabold tabnums ${tone}`}>{value}</div>
    </div>
  );
}
function Empty() { return <p className="font-mono text-xs text-muted">暂无数据，点「跑一轮 Loop」。</p>; }
