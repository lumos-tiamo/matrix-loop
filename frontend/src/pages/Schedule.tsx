import { useMemo, useState } from "react";
import { api, mediaSrc } from "../api/client";
import { useAsync } from "../api/hooks";
import type { DayItem, TrendItem } from "../api/types";

const BRAND: Record<string, string> = {
  askaurea: "#C6FF3A", "@AirdropEdge": "#8B5CFF", "@ClearChartsHQ": "#38BDF8", "@quiet.yield": "#F5B301",
};
const bc = (h: string | null) => BRAND[h ?? ""] ?? "#8B5CFF";
const assetId = (it: DayItem) => (it.type === "video" ? parseInt(it.id.slice(1), 10) : 0);

/* ---- B-layer verified trends panel ---- */
function TrendsPanel() {
  const [open, setOpen] = useState(false);
  const trends = useAsync<TrendItem[]>(() => api.getTrends(), []);
  const list = trends.data ?? [];
  return (
    <div className="glass">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-4 py-2.5 text-left font-mono text-xs">
        <span className="text-lime">🔥 B层已核实热点</span><span className="text-dim">{list.length} 条 · 喂 A 脑(含来源)</span>
        <span className="flex-1" /><span className="text-dim">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="grid gap-2 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
          {list.map((t) => (
            <div key={t.id} className="rounded-lg border border-line/60 p-2">
              <p className="text-xs text-text">{t.distilled_topic || t.title}</p>
              <div className="mt-1 flex gap-2 font-mono text-[10px] text-dim">
                <span style={{ color: bc(null) }}>{t.niche}</span>
                {t.url && <a href={t.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">来源↗</a>}
                <span className="flex-1" /><span>{t.score ? `真实性 ${Math.round(t.score)}` : ""}</span>
              </div>
            </div>
          ))}
          {!list.length && <div className="col-span-full font-mono text-[11px] text-dim">还没有热点。点「🤖全自动」会先研究再出片。</div>}
        </div>
      )}
    </div>
  );
}

/* ---- one expandable content card ---- */
function Card({ it, onAct }: { it: DayItem; onAct: (label: string, fn: () => Promise<unknown>) => void }) {
  const [open, setOpen] = useState(false);
  const isVideo = it.type === "video";
  const badge = isVideo ? "🎬" : "🖼";
  return (
    <div className="glass">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        <span>{badge}</span>
        <span className="font-mono text-[11px] text-dim">{(it.posting_time || "").slice(11) || "图文"}</span>
        <span className="flex-1 truncate text-xs text-text">{it.title || it.caption || "(无标题)"}</span>
        {it.source_score != null && <span className="rounded bg-lime/[.12] px-1.5 py-0.5 font-mono text-[10px] text-lime">真 {Math.round(it.source_score)}</span>}
        <span className={`font-mono text-[10px] ${it.review_status === "approved" ? "text-lime" : it.review_status === "rejected" ? "text-red-400" : "text-amber-400"}`}>
          {it.review_status === "approved" ? "已采纳" : it.review_status === "rejected" ? "已驳回" : "待审"}
        </span>
        {it.is_seed && <span className="rounded bg-black/40 px-1 font-mono text-[9px] text-lime">种子</span>}
        <span className="text-dim">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="grid gap-3 border-t border-line p-3 md:grid-cols-[200px_1fr]">
          <div>
            {isVideo && it.media_url ? (
              <video src={mediaSrc(it.media_url) || ""} controls muted playsInline preload="metadata" className="w-full rounded-lg" />
            ) : it.slide_urls.length ? (
              <div className="flex gap-1.5 overflow-x-auto">
                {it.slide_urls.map((u, i) => <img key={i} src={mediaSrc(u) || u} loading="lazy" className="h-40 w-auto rounded border border-line/60" />)}
              </div>
            ) : <div className="flex h-40 items-center justify-center rounded bg-black/30 font-mono text-[11px] text-dim">无预览</div>}
          </div>
          <div className="space-y-2 text-xs">
            <Row k="🕒 发布时间">{it.posting_time || "—"}</Row>
            <Row k="📝 脚本">{it.script ? <span className="whitespace-pre-wrap text-muted">{it.script}</span> : "—"}</Row>
            <Row k="📣 发布配套">
              <div className="text-muted">{it.caption || "—"}</div>
              {it.hashtags?.length ? <div className="mt-1 text-dim">{it.hashtags.join(" ")}</div> : null}
              {it.external_link_slot && <div className="mt-1 font-mono text-[11px] text-dim">外链位: {it.external_link_slot}</div>}
            </Row>
            <Row k="💡 idea 来源">{it.source_url ? <a href={it.source_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline break-all">{it.source_url}</a> : "—"}</Row>
            <Row k="✅ 真实性评估">{it.source_score != null ? `${Math.round(it.source_score)}/100 · 全网 web_search 核实 + 来源可查` : "—(旧内容/未标注来源)"}</Row>
            <div className="flex flex-wrap gap-1.5 pt-1 font-mono text-[11px]">
              <button onClick={() => navigator.clipboard?.writeText(it.caption || "")} className="rounded border border-line px-2 py-1 text-muted hover:border-lime hover:text-lime">复制文案</button>
              {isVideo && <>
                <button onClick={() => onAct("regen", () => api.regenerateVideo(assetId(it)))} className="rounded border border-line px-2 py-1 text-muted hover:border-lime hover:text-lime">重新生成</button>
                <button onClick={() => onAct("edit", () => api.queuePalmier(assetId(it)))} className="rounded border border-line px-2 py-1 text-muted hover:border-sky-400 hover:text-sky-400">剪辑</button>
                <button disabled={it.review_status === "approved"} onClick={() => onAct("ok", () => api.setVideoReview(assetId(it), "approved"))} className="rounded border border-line px-2 py-1 text-muted hover:border-lime hover:text-lime disabled:opacity-40">采纳</button>
                <button disabled={it.review_status === "rejected"} onClick={() => onAct("no", () => api.setVideoReview(assetId(it), "rejected"))} className="rounded border border-line px-2 py-1 text-muted hover:border-red-400 hover:text-red-400 disabled:opacity-40">驳回</button>
              </>}
              {!isVideo && it.account_id && <button onClick={() => onAct("regen", () => api.generateCarousels(it.account_id!))} className="rounded border border-line px-2 py-1 text-muted hover:border-lime hover:text-lime">重新生成图文</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-2">
      <div className="font-mono text-[11px] text-dim">{k}</div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/* ---- month calendar ---- */
function Calendar({ counts, sel, onSel }: { counts: Record<string, number>; sel: string; onSel: (d: string) => void }) {
  const dates = Object.keys(counts).sort();
  const seed = sel || dates[dates.length - 1] || new Date().toISOString().slice(0, 10);
  const [ym, setYm] = useState(seed.slice(0, 7));
  const [y, m] = ym.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const startDow = (first.getDay() + 6) % 7;   // Monday-first
  const daysIn = new Date(y, m, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysIn; d++) cells.push(d);
  const nav = (delta: number) => { const nd = new Date(y, m - 1 + delta, 1); setYm(`${nd.getFullYear()}-${String(nd.getMonth() + 1).padStart(2, "0")}`); };
  const key = (d: number) => `${ym}-${String(d).padStart(2, "0")}`;
  return (
    <div className="glass p-3">
      <div className="mb-2 flex items-center gap-3 font-mono text-xs">
        <button onClick={() => nav(-1)} className="rounded border border-line px-2 text-muted hover:text-text">‹</button>
        <span className="font-display text-sm font-bold">{y} 年 {m} 月</span>
        <button onClick={() => nav(1)} className="rounded border border-line px-2 text-muted hover:text-text">›</button>
        {sel && <button onClick={() => onSel("")} className="ml-2 text-dim hover:text-lime">显示全部日期 ✕</button>}
        <span className="flex-1" />
        <span className="text-dim">有内容的日期高亮 · 点击查看当天</span>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center font-mono text-[11px]">
        {["一", "二", "三", "四", "五", "六", "日"].map((w) => <div key={w} className="py-1 text-dim">{w}</div>)}
        {cells.map((d, i) => {
          if (!d) return <div key={i} />;
          const k = key(d), c = counts[k] || 0, on = sel === k;
          return (
            <button key={i} onClick={() => c && onSel(on ? "" : k)} disabled={!c}
              className={`aspect-square rounded-lg border p-1 ${on ? "border-lime bg-lime/[.15]" : c ? "border-lime/40 bg-lime/[.06] hover:bg-lime/[.12]" : "border-line/40 text-dim"}`}>
              <div className={c ? "text-text" : ""}>{d}</div>
              {c > 0 && <div className="text-[9px] text-lime">{c}</div>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ---- page ---- */
export function Schedule() {
  const dp = useAsync(() => api.getDayPlan(), [], 15000);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fType, setFType] = useState<"all" | "video" | "carousel">("all");
  const [fAcc, setFAcc] = useState("all");
  const [q, setQ] = useState("");
  const [selDate, setSelDate] = useState("");

  const all = dp.data ?? [];
  const handles = useMemo(() => [...new Set(all.map((i) => i.handle).filter(Boolean))] as string[], [all]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of all) if (i.date) c[i.date] = (c[i.date] || 0) + 1;
    return c;
  }, [all]);
  const query = q.trim().toLowerCase();
  const items = all.filter((i) =>
    (fType === "all" || i.type === fType) &&
    (fAcc === "all" || i.handle === fAcc) &&
    (!selDate || i.date === selDate) &&
    (!query || (i.title || "").toLowerCase().includes(query) || (i.script || "").toLowerCase().includes(query) || (i.handle || "").toLowerCase().includes(query)));

  // group: date -> handle -> items
  const byDate = useMemo(() => {
    const m = new Map<string, Map<string, DayItem[]>>();
    for (const it of items) {
      const d = it.date || "未排期";
      if (!m.has(d)) m.set(d, new Map());
      const h = it.handle || "?";
      const hm = m.get(d)!;
      if (!hm.has(h)) hm.set(h, []);
      hm.get(h)!.push(it);
    }
    return [...m.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [items]);

  async function act(_label: string, fn: () => Promise<unknown>) {
    setMsg(null);
    try { await fn(); await dp.reload(); } catch (e) { setMsg(String(e)); }
  }
  async function trigger(fn: () => Promise<unknown>, note: string) {
    setBusy(true); setMsg(null);
    try { await fn(); setMsg(note); } catch (e) { setMsg(String(e)); }
    finally { setTimeout(() => setBusy(false), 3000); }
  }

  const vids = all.filter((i) => i.type === "video" && !i.is_seed).length;
  const imgs = all.filter((i) => i.type === "carousel").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="font-display text-xl font-extrabold">排期</h1>
        <span className="font-mono text-xs text-dim">按天 · 分账号/平台 · 视频{vids} 图文{imgs} · 展开看脚本/配套/来源/真实性</span>
        <div className="flex-1" />
        <button onClick={() => trigger(() => api.runFullDaily(4), "🤖 已启动全自动一天(研究→出片→排期,约30-45分)")} disabled={busy}
          className="rounded-lg border border-lime bg-lime/[.12] px-3 py-[6px] font-mono text-xs font-bold text-lime hover:bg-lime/[.2] disabled:opacity-50">🤖 全自动跑一天</button>
        <button onClick={() => trigger(() => api.generateDaily(4), "⚡ 已启动出片(基于已核实热点)")} disabled={busy}
          className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text disabled:opacity-50">⚡ 仅出片</button>
        <button onClick={() => trigger(() => api.generateCarousels(), "🖼 已启动图文(4账号,真数据)")} disabled={busy}
          className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text disabled:opacity-50">🖼 图文</button>
        <button onClick={() => dp.reload()} className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text">刷新</button>
      </div>

      <TrendsPanel />
      <Calendar counts={counts} sel={selDate} onSel={setSelDate} />

      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="🔎 搜脚本/标题/账号" className="w-44 rounded border border-line bg-transparent px-2 py-1 text-text placeholder:text-dim" />
        <select value={fAcc} onChange={(e) => setFAcc(e.target.value)} className="rounded border border-line bg-transparent px-2 py-1 text-muted">
          <option value="all">全部账号</option>{handles.map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
        {(["all", "video", "carousel"] as const).map((t) => (
          <button key={t} onClick={() => setFType(t)} className={`rounded px-2.5 py-1 ${fType === t ? "bg-lime/[.12] text-lime" : "text-dim hover:text-text"}`}>
            {t === "all" ? "全部" : t === "video" ? "视频" : "图文"}
          </button>
        ))}
        <span className="text-dim">共 {items.length} 条</span>
      </div>

      {msg && <div className="rounded-lg border border-lime/40 bg-lime/[.08] px-3 py-2 font-mono text-xs text-lime">{msg}</div>}
      {dp.loading && !all.length && <div className="font-mono text-sm text-dim">加载中…</div>}
      {!dp.loading && !items.length && <div className="rounded-lg border border-line px-4 py-8 text-center font-mono text-sm text-dim">没有内容。点「🤖 全自动跑一天」。</div>}

      {byDate.map(([date, hm]) => (
        <section key={date} className="space-y-3">
          <div className="flex items-center gap-2 border-b border-line pb-1">
            <span className="font-display text-base font-bold">{date}</span>
            <span className="font-mono text-[11px] text-dim">{[...hm.values()].reduce((n, a) => n + a.length, 0)} 条</span>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {[...hm.entries()].map(([handle, list]) => (
              <div key={handle} className="glass glass-hover p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold text-black" style={{ background: bc(handle) }}>{handle}</span>
                  <span className="font-mono text-[10px] text-dim">{list[0]?.platform} · {list.length} 条</span>
                </div>
                <div className="space-y-1.5">
                  {list.sort((a, b) => (a.posting_time < b.posting_time ? -1 : 1)).map((it) => <Card key={it.id} it={it} onAct={act} />)}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
