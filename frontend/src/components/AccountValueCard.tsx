import { useState } from "react";
import { Link } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import type { AccountListItem } from "../api/types";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

const STATUS_TAG: Record<string, { label: string; bg: string; color: string }> = {
  ok: { label: "见效", bg: "rgba(56,224,138,.15)", color: "#38E08A" },
  adopted: { label: "见效", bg: "rgba(56,224,138,.15)", color: "#38E08A" },
  no_progress: { label: "需介入", bg: "rgba(255,176,32,.16)", color: "#FFB020" },
  error: { label: "错误", bg: "rgba(255,92,122,.16)", color: "#FF5C7A" },
  budget_stop: { label: "超预算", bg: "rgba(255,92,122,.16)", color: "#FF5C7A" },
};

/** ring color follows score: lime (good) -> cyan (mid) -> warn (low). */
function ringColor(score: number): string {
  if (score >= 70) return "#B6FF3C";
  if (score >= 50) return "#4CD4F0";
  return "#FFB020";
}

function fmtFollowers(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K`;
  return String(n);
}

/** Deterministic pseudo-sparkline seeded from the account id, trending toward the score. */
function sparkFor(a: AccountListItem): number[] {
  const base = a.latest_composite_score ?? 40;
  const seed = a.id * 9301 + 49297;
  return Array.from({ length: 7 }, (_, i) => {
    const wobble = (((seed + i * 233) % 100) / 100 - 0.5) * 12;
    const drift = (i / 6) * (base - 40) * 0.4;
    return Math.max(0, base - 20 + drift + wobble);
  });
}

export function AccountValueCard({ account, style, onRan }: { account: AccountListItem; style?: React.CSSProperties; onRan?: () => void }) {
  const [running, setRunning] = useState(false);

  // Run one account's Loop without leaving the card (the card is a <Link>, so stop the click
  // from navigating). Each card runs independently — you can fire several accounts at once.
  async function runOne(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (running) return;
    setRunning(true);
    try { await api.triggerLoop(account.id); onRan?.(); }
    catch { /* surfaced by the list on reload */ }
    finally { setRunning(false); }
  }

  const score = account.latest_composite_score ?? 0;
  const color = ringColor(score);
  const status = account.latest_loop_status ?? "";
  const tag = STATUS_TAG[status];
  const attention = status === "no_progress" || status === "error" || status === "budget_stop";
  const spark = sparkFor(account);

  const sparkOption = {
    backgroundColor: "transparent",
    grid: { top: 4, right: 2, bottom: 2, left: 2 },
    xAxis: { type: "category", show: false, boundaryGap: false, data: spark.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    series: [
      { type: "line", data: spark, smooth: true, symbol: "none", lineStyle: { color, width: 2 }, areaStyle: { color, opacity: 0.1 } },
    ],
  };

  return (
    <Link
      to={`/accounts/${account.id}`}
      className="block glass glass-hover p-4 rise"
      style={{ borderColor: attention ? "rgba(255,176,32,.4)" : undefined, ...style }}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex h-[52px] w-[52px] items-center justify-center rounded-full"
          style={{ background: `conic-gradient(${color} ${score}%, #232B3C 0)` }}
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-panel font-mono text-sm font-semibold tabnums">
            {Math.round(score)}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <b className="truncate">{account.handle}</b>
            {tag && (
              <span
                className="shrink-0 rounded-md px-[7px] py-[2px] font-mono text-[10px]"
                style={{ background: tag.bg, color: tag.color }}
              >
                {tag.label}
              </span>
            )}
          </div>
          <div className="mt-[2px] truncate font-mono text-[10px] uppercase text-muted">
            {PLATFORM_LABEL[account.platform] ?? account.platform}
            {account.vertical ? ` · ${account.vertical}` : ""}
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-[14px] font-mono text-[11px] text-muted tabnums">
        <span>粉丝 {fmtFollowers(account.latest_followers)}</span>
        <span className="text-muted">数据 {account.source_tier ?? "—"}</span>
        <span className="flex-1" />
        <button
          onClick={runOne}
          disabled={running}
          title="只跑这个账号一轮 Loop"
          className="rounded-md border border-lime/50 bg-lime/[.08] px-[9px] py-[3px] font-mono text-[10px] text-lime transition-colors hover:bg-lime/[.16] disabled:opacity-50"
        >
          {running ? "⏳ 跑…" : "⚡ 跑一轮"}
        </button>
      </div>
      <div className="mt-2 h-[34px]">
        <ReactECharts option={sparkOption} style={{ height: 34 }} opts={{ renderer: "svg" }} />
      </div>
    </Link>
  );
}
