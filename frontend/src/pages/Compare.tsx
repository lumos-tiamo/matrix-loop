import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { AccountDetail, AccountListItem } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { ScoreRadar } from "../components/ScoreRadar";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

function ringColor(score: number): string {
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

function parseIds(raw: string | null): number[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0)
    .slice(0, 3);
}

/** One account column: value-score ring + KPIs + evaluation radar. */
function CompareColumn({ id, delay }: { id: number; delay: number }) {
  const { data, loading, error } = useAsync(() => api.getAccount(id), [id]);

  if (loading) return <ChartCard className="rise" style={{ animationDelay: `${delay}ms` }}><p className="font-mono text-xs text-muted">加载中…</p></ChartCard>;
  if (error || !data) return <ChartCard className="rise" style={{ animationDelay: `${delay}ms` }}><p className="font-mono text-xs text-alert">加载失败：{error}</p></ChartCard>;

  const d: AccountDetail = data;
  const latestSnap = [...d.snapshots].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const latestRun = [...d.loop_runs].sort((a, b) => b.ts.localeCompare(a.ts))[0];
  const score = latestRun?.evaluation?.composite_score ?? 0;
  const color = ringColor(score);

  return (
    <ChartCard className="rise" style={{ animationDelay: `${delay}ms` }}>
      {/* header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-[56px] w-[56px] items-center justify-center rounded-full"
          style={{ background: `conic-gradient(${color} ${score}%, #232B3C 0)` }}
        >
          <span className="flex h-[44px] w-[44px] items-center justify-center rounded-full bg-panel font-mono text-base font-semibold tabnums" style={{ color }}>
            {Math.round(score)}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <b className="block truncate font-display text-[15px]">{d.handle}</b>
          <div className="mt-[2px] truncate font-mono text-[10px] uppercase text-muted">
            {PLATFORM_LABEL[d.platform] ?? d.platform}
            {d.vertical ? ` · ${d.vertical}` : ""}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs tabnums">
        <Kpi label="粉丝" value={fmtFollowers(latestSnap?.followers)} tone="text-lime" />
        <Kpi label="互动率" value={latestSnap?.engagement_rate != null ? `${(latestSnap.engagement_rate * 100).toFixed(1)}%` : "—"} tone="text-cyan" />
        <Kpi label="爆文率" value={latestSnap?.hit_rate != null ? `${(latestSnap.hit_rate * 100).toFixed(0)}%` : "—"} tone="text-violet" />
        <Kpi label="转化" value={String(latestSnap?.conversions ?? "—")} tone="text-pink" />
      </div>

      {/* radar */}
      <div className="mt-3">
        <div className="mb-1 font-mono text-[10px] uppercase text-muted">评估拆解</div>
        {latestRun?.evaluation ? (
          <ScoreRadar breakdown={latestRun.evaluation.breakdown} />
        ) : (
          <p className="font-mono text-xs text-muted">暂无评估，先跑一轮 Loop。</p>
        )}
      </div>
    </ChartCard>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-3 py-2">
      <div className="text-[10px] uppercase text-muted">{label}</div>
      <div className={`mt-[2px] text-sm ${tone}`}>{value}</div>
    </div>
  );
}

export function Compare() {
  const [params, setParams] = useSearchParams();
  const selected = useMemo(() => parseIds(params.get("ids")), [params]);
  const accounts = useAsync(() => api.listAccounts(), []);
  const acctList = useMemo(() => accounts.data ?? [], [accounts.data]);

  function toggle(id: number) {
    const set = new Set(selected);
    if (set.has(id)) set.delete(id);
    else if (set.size < 3) set.add(id);
    const next = [...set];
    if (next.length) params.set("ids", next.join(","));
    else params.delete("ids");
    setParams(params, { replace: true });
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 px-1 pb-4 pt-[10px]">
        <span className="font-display text-[13px] font-bold text-muted">⚖️ 账号对比</span>
        <span className="font-mono text-[11px] text-muted">最多选 3 个</span>
        <div className="flex-1" />
      </div>

      {/* account picker */}
      {accounts.loading && <div className="px-1 font-mono text-muted">加载账号…</div>}
      {accounts.error && <div className="px-1 font-mono text-alert">加载失败：{accounts.error}</div>}
      {acctList.length > 0 && (
        <div className="mb-[14px] flex flex-wrap gap-2 px-[2px]">
          {acctList.map((a: AccountListItem) => {
            const on = selected.includes(a.id);
            const full = !on && selected.length >= 3;
            return (
              <button
                key={a.id}
                disabled={full}
                onClick={() => toggle(a.id)}
                className={`rounded-full border px-3 py-[5px] font-mono text-[11px] disabled:opacity-40 ${
                  on ? "border-lime bg-lime/[.08] text-lime" : "border-line bg-panel text-muted"
                }`}
              >
                {a.handle}
              </button>
            );
          })}
        </div>
      )}

      {selected.length === 0 ? (
        <p className="px-[2px] font-mono text-xs text-muted">选 2-3 个账号开始对比。</p>
      ) : (
        <div
          className="grid gap-[14px]"
          style={{ gridTemplateColumns: `repeat(${Math.min(selected.length, 3)}, minmax(0, 1fr))` }}
        >
          {selected.map((id, i) => (
            <CompareColumn key={id} id={id} delay={i * 60} />
          ))}
        </div>
      )}
    </div>
  );
}
