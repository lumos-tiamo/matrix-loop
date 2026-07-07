import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { TrendChart } from "../components/TrendChart";
import { ScoreRadar } from "../components/ScoreRadar";
import { LoopTimeline } from "../components/LoopTimeline";
import { ReviewPanel } from "../components/ReviewPanel";

export function AccountDetail() {
  const { id } = useParams();
  const accountId = Number(id);
  const { data, loading, error, reload } = useAsync(() => api.getAccount(accountId), [accountId]);
  const [actionError, setActionError] = useState<string | null>(null);

  if (loading) return <div className="font-mono text-muted">加载中…</div>;
  if (error || !data) return <div className="font-mono text-alert">加载失败：{error}</div>;

  const latestSnap = [...data.snapshots].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const latestRun = [...data.loop_runs].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const score = latestRun?.evaluation?.composite_score ?? null;

  const runLoop = async () => {
    setActionError(null);
    try { await api.triggerLoop(accountId); reload(); }
    catch (e) { setActionError(String(e)); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="font-mono text-xs text-muted">{data.platform} · {data.vertical ?? "—"}</div>
          <h1 className="font-display text-2xl">{data.handle}</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="font-mono text-[11px] uppercase text-muted">价值分</div>
            <div className="font-display text-4xl text-accent tabnums">{score != null ? score.toFixed(0) : "—"}</div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <button onClick={runLoop} className="font-mono text-xs border border-accent text-accent rounded px-3 py-2 hover:bg-accent hover:text-bg transition">跑一轮 Loop</button>
            {actionError && <p className="font-mono text-xs text-alert">{actionError}</p>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-sm">
        <Kpi label="粉丝" value={latestSnap?.followers?.toLocaleString() ?? "—"} />
        <Kpi label="互动率" value={latestSnap?.engagement_rate != null ? `${(latestSnap.engagement_rate * 100).toFixed(1)}%` : "—"} />
        <Kpi label="爆文率" value={latestSnap?.hit_rate != null ? `${(latestSnap.hit_rate * 100).toFixed(0)}%` : "—"} />
        <Kpi label="转化" value={String(latestSnap?.conversions ?? "—")} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="涨粉趋势"><TrendChart snapshots={data.snapshots} /></Panel>
        <Panel title="评估拆解">{latestRun?.evaluation ? <ScoreRadar breakdown={latestRun.evaluation.breakdown} /> : <Empty />}</Panel>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="Loop 历史">{data.loop_runs.length ? <LoopTimeline runs={data.loop_runs} /> : <Empty />}</Panel>
        <Panel title="本轮待审产出">{latestRun ? <ReviewPanel run={latestRun} onChange={reload} /> : <Empty />}</Panel>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="text-[11px] uppercase text-muted">{label}</div>
      <div className="text-lg mt-1 tabnums">{value}</div>
    </div>
  );
}
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-panel p-4 rise">
      <h2 className="font-display text-sm mb-3">{title}</h2>
      {children}
    </section>
  );
}
function Empty() { return <p className="font-mono text-xs text-muted">暂无数据，点「跑一轮 Loop」。</p>; }
