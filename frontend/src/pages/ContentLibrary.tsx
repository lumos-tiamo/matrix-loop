import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { ChartCard } from "../components/ChartCard";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

const PLATFORM_TONE: Record<string, string> = {
  xiaohongshu: "#FF6FB5",
  douyin: "#4CD4F0",
  tiktok: "#A78BFA",
  twitter: "#4CD4F0",
  x: "#4CD4F0",
  weixin_video: "#38E08A",
  wechat_video: "#38E08A",
};

const CHIPS = [
  { value: "", label: "全部" },
  { value: "xiaohongshu", label: "小红书" },
  { value: "douyin", label: "抖音" },
  { value: "tiktok", label: "TikTok" },
  { value: "twitter", label: "X" },
];

function fmtNum(n: number | null): string {
  if (n == null) return "—";
  if (n >= 10000) return `${(n / 10000).toFixed(1)}W`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

export function ContentLibrary() {
  const [platform, setPlatform] = useState("");
  const [search, setSearch] = useState("");
  const content = useAsync(() => api.getContent(platform ? { platform } : undefined), [platform]);

  const items = useMemo(() => {
    const raw = content.data ?? [];
    const q = search.trim().toLowerCase();
    return [...raw]
      .filter((i) => (q ? (i.topic ?? "").toLowerCase().includes(q) || i.account_handle.toLowerCase().includes(q) : true))
      .sort((a, b) => (b.views ?? 0) - (a.views ?? 0));
  }, [content.data, search]);

  const maxViews = items.reduce((m, i) => Math.max(m, i.views ?? 0), 1);

  return (
    <div>
      {/* header / filter row */}
      <div className="flex flex-wrap items-center gap-3 px-1 pb-4 pt-[10px]">
        <span className="font-display text-[13px] font-bold text-muted">🔥 爆文库</span>
        <div className="flex-1" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔍 搜索选题 / 账号…"
          className="min-w-[220px] rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text placeholder:text-muted focus:border-lime focus:outline-none"
        />
        {CHIPS.map((c) => {
          const on = platform === c.value;
          return (
            <button
              key={c.value || "all"}
              onClick={() => setPlatform(c.value)}
              className={`rounded-full border px-3 py-[5px] font-mono text-[11px] ${
                on ? "border-lime bg-lime/[.08] text-lime" : "border-line bg-panel text-muted"
              }`}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {content.loading && <div className="px-1 font-mono text-muted">加载中…</div>}
      {content.error && <div className="px-1 font-mono text-alert">加载失败：{content.error}</div>}

      {content.data && (
        <>
          <div className="mb-[10px] flex flex-wrap items-center gap-[10px] px-[2px]">
            <span className="rounded-full border border-line px-2 py-[2px] font-mono text-[10px] text-muted">
              共 {items.length} 篇 · 按浏览量排序
            </span>
            {items.length > 0 && (
              <span className="rounded-full border border-lime/40 bg-lime/[.06] px-2 py-[2px] font-mono text-[10px] text-lime">
                🥇 置顶爆文 {fmtNum(items[0].views)} 播放
              </span>
            )}
          </div>

          {items.length === 0 ? (
            <p className="px-[2px] font-mono text-xs text-muted">没有匹配的内容。</p>
          ) : (
            <div className="grid gap-[14px] sm:grid-cols-2 lg:grid-cols-3">
              {items.map((it, i) => {
                const tone = PLATFORM_TONE[it.platform] ?? "#4CD4F0";
                const pct = Math.max(4, Math.round(((it.views ?? 0) / maxViews) * 100));
                const isTop = i === 0;
                return (
                  <ChartCard
                    key={it.id}
                    className="rise"
                    glow={isTop}
                    style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className="shrink-0 rounded-md px-[7px] py-[2px] font-mono text-[10px]"
                        style={{ background: `${tone}22`, color: tone }}
                      >
                        {PLATFORM_LABEL[it.platform] ?? it.platform}
                      </span>
                      {isTop && (
                        <span className="shrink-0 font-mono text-[10px] text-lime">🥇 TOP</span>
                      )}
                    </div>
                    <div
                      data-testid="content-topic"
                      className="mt-[10px] line-clamp-2 font-display text-[15px] font-bold text-text"
                    >
                      {it.topic ?? "（无题）"}
                    </div>
                    <Link
                      to={`/accounts/${it.account_id}`}
                      className="mt-[6px] block truncate font-mono text-[11px] text-muted hover:text-lime"
                    >
                      {it.account_handle}
                    </Link>

                    {/* views bar */}
                    <div className="mt-3 h-[5px] overflow-hidden rounded bg-line">
                      <i className="block h-full rounded" style={{ width: `${pct}%`, background: tone }} />
                    </div>
                    <div className="mt-[10px] flex items-center gap-4 font-mono text-[11px] tabnums">
                      <span className="text-text">👁 {fmtNum(it.views)}</span>
                      <span className="text-pink">♥ {fmtNum(it.likes)}</span>
                      <span className="text-muted">💬 {fmtNum(it.comments)}</span>
                    </div>
                  </ChartCard>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
