import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { AccountListItem } from "../api/types";
import { KpiCard } from "../components/KpiCard";
import { HeatmapCard } from "../components/HeatmapCard";
import { TrendCard } from "../components/TrendCard";
import { AlertCenter } from "../components/AlertCenter";
import { MoversCard } from "../components/MoversCard";
import { PositioningDonut } from "../components/PositioningDonut";
import { AccountCard } from "../components/AccountCard";
import { FilterBar, type SortKey } from "../components/FilterBar";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

const CHIPS = [
  { value: "", label: "全部" },
  { value: "xiaohongshu", label: "小红书" },
  { value: "douyin", label: "抖音" },
  { value: "tiktok", label: "TikTok" },
  { value: "twitter", label: "X" },
];

function fmtSigned(n: number): string {
  const sign = n >= 0 ? "+" : "-";
  const abs = Math.abs(n);
  const v = abs >= 1000 ? `${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}K` : String(abs);
  return `${sign}${v}`;
}

export function Overview() {
  const overview = useAsync(() => api.getOverview(), []);
  const accounts = useAsync(() => api.listAccounts(), []);

  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState("");
  const [sort, setSort] = useState<SortKey>("score");
  const [running, setRunning] = useState(false);

  const acctList = useMemo(() => accounts.data ?? [], [accounts.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return acctList
      .filter((a) => (platform ? a.platform === platform : true))
      .filter((a) =>
        q
          ? a.handle.toLowerCase().includes(q) || (a.vertical ?? "").toLowerCase().includes(q)
          : true,
      )
      .sort((a, b) =>
        sort === "score"
          ? (b.latest_composite_score ?? -1) - (a.latest_composite_score ?? -1)
          : (b.latest_followers ?? -1) - (a.latest_followers ?? -1),
      );
  }, [acctList, platform, search, sort]);

  // counts per platform for the section-head pills
  const platformCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of acctList) m.set(a.platform, (m.get(a.platform) ?? 0) + 1);
    return [...m.entries()];
  }, [acctList]);

  async function runBatch() {
    setRunning(true);
    try {
      await api.batchRun(true);
      overview.reload();
      accounts.reload();
    } catch (e) {
      // surface but don't crash
      console.error(e);
    } finally {
      setRunning(false);
    }
  }

  const ov = overview.data;
  const loading = overview.loading || accounts.loading;
  const error = overview.error || accounts.error;

  return (
    <div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        platform={platform}
        onPlatform={setPlatform}
        chips={CHIPS}
        sort={sort}
        onSort={setSort}
        onRunBatch={runBatch}
        running={running}
      />

      {loading && <div className="px-1 font-mono text-muted">加载中…</div>}
      {error && <div className="px-1 font-mono text-alert">加载失败：{error}</div>}

      {ov && (
        <>
          {/* KPI ROW */}
          <div className="mb-[14px] grid grid-cols-2 gap-[14px] md:grid-cols-5">
            <KpiCard
              label="账号总数"
              value={String(ov.kpis.total_accounts)}
              delta={`覆盖 ${ov.kpis.platforms} 平台`}
              deltaTone="neutral"
              tone="text"
              spark={[6, 8, 7, 12, 11, 15, 18]}
              style={{ animationDelay: "0ms" }}
            />
            <KpiCard
              label="平均价值分"
              value={String(Math.round(ov.kpis.avg_score))}
              delta={`当前均值 ${ov.kpis.avg_score}`}
              deltaTone="up"
              tone="lime"
              glow
              spark={[8, 7, 11, 10, 14, 16, 19]}
              style={{ animationDelay: "60ms" }}
            />
            <KpiCard
              label="本周净涨粉"
              value={fmtSigned(
                ov.top_movers.reduce((s, m) => s + m.delta_followers, 0),
              )}
              delta={`Top ${ov.top_movers.length} 账号`}
              deltaTone="up"
              tone="violet"
              spark={[4, 6, 5, 9, 12, 14, 17]}
              style={{ animationDelay: "120ms" }}
            />
            <KpiCard
              label="需介入"
              value={String(ov.kpis.needs_attention)}
              delta="连续无进展"
              deltaTone={ov.kpis.needs_attention > 0 ? "down" : "neutral"}
              tone="warn"
              spark={[16, 14, 15, 12, 10, 9, 8]}
              style={{ animationDelay: "180ms" }}
            />
            <KpiCard
              label="待审产出"
              value={String(ov.kpis.pending_review)}
              delta="草稿+建议"
              deltaTone="neutral"
              tone="cyan"
              spark={[9, 12, 10, 13, 11, 14, 12]}
              style={{ animationDelay: "240ms" }}
            />
          </div>

          {/* HEATMAP + TREND */}
          <div className="mb-[14px] grid gap-[14px] lg:grid-cols-[1.35fr_1fr]">
            <HeatmapCard data={ov.platform_health} style={{ animationDelay: "120ms" }} />
            <TrendCard trend={ov.trend} style={{ animationDelay: "180ms" }} />
          </div>

          {/* ALERTS + MOVERS + DONUT */}
          <div className="mb-[14px] grid gap-[14px] lg:grid-cols-3">
            <AlertCenter alerts={ov.alerts} style={{ animationDelay: "160ms" }} />
            <MoversCard movers={ov.top_movers} style={{ animationDelay: "220ms" }} />
            <PositioningDonut dist={ov.positioning_distribution} style={{ animationDelay: "280ms" }} />
          </div>
        </>
      )}

      {/* ACCOUNT MATRIX */}
      {accounts.data && (
        <>
          <div className="mb-[10px] mt-[6px] flex flex-wrap items-center gap-[10px] px-[2px]">
            <span className="font-display text-[13px] font-bold text-muted">账号矩阵</span>
            {platformCounts.map(([p, n]) => (
              <span key={p} className="rounded-full border border-line px-2 py-[2px] font-mono text-[10px] text-muted">
                {PLATFORM_LABEL[p] ?? p} · {n}
              </span>
            ))}
            <div className="flex-1" />
            <span className="rounded-full border border-line px-2 py-[2px] font-mono text-[10px] text-muted">
              ⇅ {sort === "score" ? "价值分" : "粉丝"}
            </span>
            <span className="rounded-full border border-line px-2 py-[2px] font-mono text-[10px] text-muted">
              {filtered.length} / {acctList.length}
            </span>
          </div>

          {filtered.length === 0 ? (
            <p className="px-[2px] font-mono text-xs text-muted">没有匹配的账号。</p>
          ) : (
            <div className="grid gap-[14px] sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((a: AccountListItem, i) => (
                <AccountCard key={a.id} account={a} style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
