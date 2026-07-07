import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { AccountListItem } from "../api/types";
import { StatTile } from "../components/StatTile";
import { StatusDot } from "../components/StatusDot";
import { ScoreBar } from "../components/ScoreBar";

type SortKey = "score" | "followers";

export function Overview() {
  const { data, loading, error } = useAsync(() => api.listAccounts(), []);
  const [sort, setSort] = useState<SortKey>("score");

  const accounts = useMemo(() => data ?? [], [data]);
  const needsAttention = accounts.filter((a) => a.latest_loop_status === "no_progress");
  const avgScore = accounts.length
    ? accounts.reduce((s, a) => s + (a.latest_composite_score ?? 0), 0) / accounts.length
    : 0;
  const platforms = new Set(accounts.map((a) => a.platform)).size;

  const sorted = [...accounts].sort((a, b) =>
    sort === "score"
      ? (b.latest_composite_score ?? -1) - (a.latest_composite_score ?? -1)
      : (b.latest_followers ?? -1) - (a.latest_followers ?? -1),
  );

  if (loading) return <div className="font-mono text-muted">加载中…</div>;
  if (error) return <div className="font-mono text-alert">加载失败：{error}</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="账号总数" value={String(accounts.length)} />
        <StatTile label="平均价值分" value={avgScore.toFixed(0)} accent />
        <StatTile label="需介入" value={String(needsAttention.length)} />
        <StatTile label="覆盖平台" value={String(platforms)} />
      </div>

      <section className="rounded-lg border border-line bg-panel p-4 rise">
        <h2 className="font-display text-sm mb-3">⚠️ 今天需要处理</h2>
        {needsAttention.length === 0 ? (
          <p className="font-mono text-xs text-muted">暂无需介入账号。</p>
        ) : (
          <ul className="space-y-2">
            {needsAttention.map((a) => (
              <li key={a.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
                <span className="font-mono text-sm">{a.handle} · {a.platform} · <span className="text-warn">需介入 (连续无进展)</span></span>
                <Link to={`/accounts/${a.id}`} className="font-mono text-xs text-accent hover:underline">查看 →</Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-line bg-panel overflow-hidden rise">
        <div className="flex items-center gap-4 px-4 py-2 border-b border-line font-mono text-xs text-muted">
          <span>全部账号</span>
          <button onClick={() => setSort("score")} className={sort === "score" ? "text-accent" : ""}>按价值分</button>
          <button onClick={() => setSort("followers")} className={sort === "followers" ? "text-accent" : ""}>按粉丝</button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="font-mono text-[11px] uppercase text-muted">
              <th className="text-left px-4 py-2">账号</th>
              <th className="text-left px-4 py-2">平台</th>
              <th className="text-left px-4 py-2">价值分</th>
              <th className="text-right px-4 py-2">粉丝</th>
              <th className="text-left px-4 py-2">Loop</th>
              <th className="text-left px-4 py-2">数据档位</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((a: AccountListItem) => (
              <tr key={a.id} className="border-t border-line hover:bg-line/30">
                <td className="px-4 py-2">
                  <Link to={`/accounts/${a.id}`} className="hover:text-accent">{a.handle}</Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-muted">{a.platform}</td>
                <td className="px-4 py-2"><ScoreBar score={a.latest_composite_score} /></td>
                <td className="px-4 py-2 text-right font-mono tabnums">{a.latest_followers?.toLocaleString() ?? "—"}</td>
                <td className="px-4 py-2"><StatusDot status={a.latest_loop_status} /></td>
                <td className="px-4 py-2 font-mono text-xs text-muted">{a.source_tier ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
