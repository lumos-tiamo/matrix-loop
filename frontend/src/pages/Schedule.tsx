import { useMemo, useState } from "react";
import { api, mediaSrc } from "../api/client";
import { useAsync } from "../api/hooks";
import type { ScheduleItem } from "../api/types";

const BRAND: Record<string, string> = {
  airdrops: "#8B5CFF", "crypto-trading": "#38BDF8", "defi-yield": "#F5B301", web3_ai: "#C6FF3A",
};
const brandColor = (it: ScheduleItem) => BRAND[it.vertical ?? ""] ?? "#8B5CFF";

function groupByDate(items: ScheduleItem[]): [string, ScheduleItem[]][] {
  const m = new Map<string, ScheduleItem[]>();
  for (const it of items) {
    const k = it.date || "未排期";
    if (!m.has(k)) m.set(k, []);
    m.get(k)!.push(it);
  }
  return [...m.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1)); // newest date first
}

export function Schedule() {
  const sched = useAsync(() => api.getSchedule(), [], 15000);
  const [busy, setBusy] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const items = sched.data ?? [];
  const groups = useMemo(() => groupByDate(items), [items]);

  async function act(id: number, label: string, fn: () => Promise<unknown>) {
    setBusy((b) => ({ ...b, [id]: label }));
    setMsg(null);
    try {
      await fn();
      await sched.reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy((b) => { const n = { ...b }; delete n[id]; return n; });
    }
  }

  const seedCount = items.filter((i) => i.is_seed).length;
  const genCount = items.length - seedCount;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-xl font-extrabold">排期日历</h1>
        <span className="font-mono text-xs text-dim">
          每日 16 条(4 账号 × 4)· 共 {items.length} 条(种子 {seedCount} / 日更 {genCount})
        </span>
        <div className="flex-1" />
        <button
          onClick={() => sched.reload()}
          className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text"
        >刷新</button>
      </div>

      {msg && <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 font-mono text-xs text-red-300">{msg}</div>}
      {sched.loading && !items.length && <div className="font-mono text-sm text-dim">加载中…</div>}
      {!sched.loading && !items.length && (
        <div className="rounded-lg border border-line px-4 py-8 text-center font-mono text-sm text-dim">
          还没有排期。跑一轮自动驾驶(daily_drive / run_daily_cycle)后,每日 16 条会出现在这里。
        </div>
      )}

      {groups.map(([date, list]) => (
        <section key={date} className="space-y-3">
          <div className="flex items-center gap-2 border-b border-line pb-1">
            <span className="font-display text-base font-bold">{date}</span>
            <span className="font-mono text-[11px] text-dim">{list.length} 条</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {list.map((it) => {
              const src = mediaSrc(it.media_url);
              const b = busy[it.asset_id];
              return (
                <div key={it.asset_id} className="flex flex-col overflow-hidden rounded-xl border border-line bg-white/[.02]">
                  <div className="relative aspect-[9/16] bg-black/40">
                    {src ? (
                      <video src={src} controls muted playsInline preload="metadata" className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center font-mono text-[11px] text-dim">
                        {it.asset_status === "generating" ? "生成中…" : "无成片"}
                      </div>
                    )}
                    <span
                      className="absolute left-2 top-2 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold text-black"
                      style={{ background: brandColor(it) }}
                    >{it.handle}</span>
                    {it.is_seed && (
                      <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-lime">种子</span>
                    )}
                  </div>

                  <div className="flex flex-1 flex-col gap-2 p-2.5">
                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <span className="text-dim">🕒 {it.posting_time || "未排期"}</span>
                      <span className="flex-1" />
                      <span className={it.review_status === "approved" ? "text-lime" : "text-amber-400"}>
                        {it.review_status === "approved" ? "已采纳" : it.review_status === "rejected" ? "已驳回" : "待审"}
                      </span>
                    </div>
                    {it.caption && <p className="line-clamp-2 text-xs text-muted">{it.caption}</p>}

                    <div className="mt-auto grid grid-cols-2 gap-1.5 pt-1">
                      <button
                        disabled={!!b}
                        onClick={() => act(it.asset_id, "regen", () => api.regenerateVideo(it.asset_id))}
                        className="rounded-md border border-line px-2 py-1 font-mono text-[11px] text-muted hover:border-lime hover:text-lime disabled:opacity-40"
                      >{b === "regen" ? "生成中…" : "重新生成"}</button>
                      <button
                        disabled={!!b}
                        onClick={() => act(it.asset_id, "edit", () => api.queuePalmier(it.asset_id))}
                        className="rounded-md border border-line px-2 py-1 font-mono text-[11px] text-muted hover:border-sky-400 hover:text-sky-400 disabled:opacity-40"
                      >{b === "edit" ? "排队中…" : "剪辑"}</button>
                      <button
                        disabled={!!b || it.review_status === "approved"}
                        onClick={() => act(it.asset_id, "ok", () => api.setVideoReview(it.asset_id, "approved"))}
                        className="rounded-md border border-line px-2 py-1 font-mono text-[11px] text-muted hover:border-lime hover:text-lime disabled:opacity-40"
                      >采纳</button>
                      <button
                        disabled={!!b || it.review_status === "rejected"}
                        onClick={() => act(it.asset_id, "no", () => api.setVideoReview(it.asset_id, "rejected"))}
                        className="rounded-md border border-line px-2 py-1 font-mono text-[11px] text-muted hover:border-red-400 hover:text-red-400 disabled:opacity-40"
                      >驳回</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
