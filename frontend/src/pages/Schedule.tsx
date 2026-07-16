import { useMemo, useState } from "react";
import { api, mediaSrc } from "../api/client";
import { useAsync } from "../api/hooks";
import type { ScheduleItem, TrendItem } from "../api/types";

const BRAND: Record<string, string> = {
  airdrops: "#8B5CFF", "crypto-trading": "#38BDF8", "defi-yield": "#F5B301", web3_ai: "#C6FF3A",
};
const brandColor = (v: string | null) => BRAND[v ?? ""] ?? "#8B5CFF";

function groupByDate(items: ScheduleItem[]): [string, ScheduleItem[]][] {
  const m = new Map<string, ScheduleItem[]>();
  for (const it of items) {
    const k = it.date || "未排期";
    if (!m.has(k)) m.set(k, []);
    m.get(k)!.push(it);
  }
  return [...m.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
}

/* ---------- B-layer hot-topics panel ---------- */
function TrendsPanel() {
  const [open, setOpen] = useState(false);
  const trends = useAsync<TrendItem[]>(() => api.getTrends(), []);
  const list = trends.data ?? [];
  const byNiche = useMemo(() => {
    const m = new Map<string, TrendItem[]>();
    for (const t of list) { const k = t.niche || "其他"; if (!m.has(k)) m.set(k, []); m.get(k)!.push(t); }
    return [...m.entries()];
  }, [list]);
  return (
    <div className="rounded-xl border border-line bg-white/[.02]">
      <button onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left font-mono text-xs">
        <span className="text-lime">🔥 B层已核实热点</span>
        <span className="text-dim">{list.length} 条 · 喂给 A 脑生成脚本(含来源)</span>
        <span className="flex-1" />
        <span className="text-dim">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="grid gap-3 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
          {byNiche.map(([niche, ts]) => (
            <div key={niche} className="space-y-2">
              <div className="font-mono text-[11px]" style={{ color: brandColor(niche) }}>{niche}</div>
              {ts.map((t) => (
                <div key={t.id} className="rounded-lg border border-line/60 p-2">
                  <p className="text-xs text-text">{t.distilled_topic || t.title}</p>
                  <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-dim">
                    <span>{t.source}</span>
                    {t.url && <a href={t.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">来源↗</a>}
                    <span className="flex-1" />
                    <span>{t.score ? `★${t.score.toFixed(1)}` : ""}</span>
                  </div>
                </div>
              ))}
              {!ts.length && <div className="font-mono text-[10px] text-dim">—</div>}
            </div>
          ))}
          {!list.length && <div className="col-span-full font-mono text-xs text-dim">
            还没有热点。B 层研究(agent)跑完后会灌进来,A 脑据此写脚本。
          </div>}
        </div>
      )}
    </div>
  );
}

/* ---------- one video card ---------- */
function Card({ it, onAct }: { it: ScheduleItem; onAct: (id: number, label: string, fn: () => Promise<unknown>) => void }) {
  const src = mediaSrc(it.media_url);
  const [editing, setEditing] = useState(false);
  const [cap, setCap] = useState(it.caption ?? "");
  const [time, setTime] = useState((it.posting_time || "").slice(11, 16));
  const [copied, setCopied] = useState(false);

  const saveCaption = () =>
    onAct(it.asset_id, "cap", () => api.putPublishPlan(it.asset_id, {
      caption: cap, hashtags: it.hashtags, external_link_slot: it.external_link_slot,
      external_link_text: null, posting_time: it.posting_time, status: "ready",
    }).then(() => setEditing(false)));

  const saveTime = () => {
    const d = (it.posting_time || "").slice(0, 10) || it.date;
    if (d && time) onAct(it.asset_id, "time", () => api.rescheduleAsset(it.asset_id, `${d} ${time}`));
  };

  const copy = () => { navigator.clipboard?.writeText(it.caption || ""); setCopied(true); setTimeout(() => setCopied(false), 1200); };

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-line bg-white/[.02]">
      <div className="relative aspect-[9/16] bg-black/40">
        {src ? <video src={src} controls muted playsInline preload="metadata" className="h-full w-full object-cover" />
          : <div className="flex h-full items-center justify-center font-mono text-[11px] text-dim">
              {it.asset_status === "generating" ? "生成中…" : "无成片"}</div>}
        <span className="absolute left-2 top-2 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold text-black"
          style={{ background: brandColor(it.vertical) }}>{it.handle}</span>
        {it.is_seed && <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-lime">种子</span>}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-2.5">
        <div className="flex items-center gap-1.5 font-mono text-[11px]">
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} onBlur={saveTime}
            className="w-[68px] rounded border border-line bg-transparent px-1 py-0.5 text-dim" title="改发布时间" />
          <span className="flex-1" />
          <span className={it.review_status === "approved" ? "text-lime" : it.review_status === "rejected" ? "text-red-400" : "text-amber-400"}>
            {it.review_status === "approved" ? "已采纳" : it.review_status === "rejected" ? "已驳回" : "待审"}
          </span>
        </div>

        {editing ? (
          <div className="space-y-1">
            <textarea value={cap} onChange={(e) => setCap(e.target.value)} rows={3}
              className="w-full rounded border border-line bg-transparent p-1.5 text-xs text-text" />
            <div className="flex gap-1.5">
              <button onClick={saveCaption} className="rounded border border-lime px-2 py-0.5 font-mono text-[10px] text-lime">保存</button>
              <button onClick={() => { setEditing(false); setCap(it.caption ?? ""); }} className="rounded border border-line px-2 py-0.5 font-mono text-[10px] text-dim">取消</button>
            </div>
          </div>
        ) : (
          <div className="group relative">
            <p className="line-clamp-2 text-xs text-muted">{it.caption || <span className="text-dim">（无文案,点编辑）</span>}</p>
            <div className="mt-1 flex gap-2 font-mono text-[10px] text-dim">
              <button onClick={() => setEditing(true)} className="hover:text-lime">编辑文案</button>
              <button onClick={copy} className="hover:text-lime">{copied ? "已复制✓" : "复制"}</button>
              {src && <a href={src} download className="hover:text-lime">下载</a>}
            </div>
          </div>
        )}

        <div className="mt-auto grid grid-cols-2 gap-1.5 pt-1">
          <Btn label="重新生成" it={it} onAct={onAct} fn={() => api.regenerateVideo(it.asset_id)} hover="lime" />
          <Btn label="剪辑" it={it} onAct={onAct} fn={() => api.queuePalmier(it.asset_id)} hover="sky" />
          <Btn label="采纳" it={it} onAct={onAct} fn={() => api.setVideoReview(it.asset_id, "approved")} hover="lime" disabled={it.review_status === "approved"} />
          <Btn label="驳回" it={it} onAct={onAct} fn={() => api.setVideoReview(it.asset_id, "rejected")} hover="red" disabled={it.review_status === "rejected"} />
        </div>
      </div>
    </div>
  );
}

const HOVER: Record<string, string> = {
  lime: "hover:border-lime hover:text-lime",
  sky: "hover:border-sky-400 hover:text-sky-400",
  red: "hover:border-red-400 hover:text-red-400",
};

function Btn({ label, it, onAct, fn, hover, disabled }: {
  label: string; it: ScheduleItem; hover: "lime" | "sky" | "red"; disabled?: boolean;
  onAct: (id: number, label: string, fn: () => Promise<unknown>) => void; fn: () => Promise<unknown>;
}) {
  return (
    <button disabled={disabled}
      onClick={() => onAct(it.asset_id, label, fn)}
      className={`rounded-md border border-line px-2 py-1 font-mono text-[11px] text-muted disabled:opacity-40 ${HOVER[hover]}`}>
      {label}
    </button>
  );
}

/* ---------- page ---------- */
export function Schedule() {
  const sched = useAsync(() => api.getSchedule(), [], 12000);
  const [busy, setBusy] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [fAccount, setFAccount] = useState("all");
  const [fType, setFType] = useState<"all" | "daily" | "seed">("all");
  const [genning, setGenning] = useState(false);

  const all = sched.data ?? [];
  const handles = useMemo(() => [...new Set(all.map((i) => i.handle))], [all]);
  const items = all.filter((i) =>
    (fAccount === "all" || i.handle === fAccount) &&
    (fType === "all" || (fType === "seed" ? i.is_seed : !i.is_seed)));
  const groups = useMemo(() => groupByDate(items), [items]);

  async function act(id: number, label: string, fn: () => Promise<unknown>) {
    setBusy((b) => ({ ...b, [id]: label })); setMsg(null);
    try { await fn(); await sched.reload(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy((b) => { const n = { ...b }; delete n[id]; return n; }); }
  }
  // busy state is read inside Card via a data attribute-free closure; simplest: disable during any op
  void busy;

  async function genDaily() {
    setGenning(true); setMsg(null);
    try {
      const r = await api.generateDaily(4);
      setMsg(`已启动生成 ${r.expected_new} 条(4账号×4)。渲染约需 20–35 分钟,视频会陆续出现在下方,自动刷新。`);
    } catch (e) { setMsg(String(e)); }
    finally { setTimeout(() => setGenning(false), 3000); }
  }

  const daily = all.filter((i) => !i.is_seed);
  const approved = daily.filter((i) => i.review_status === "approved").length;
  const next = [...daily].filter((i) => i.posting_time).sort((a, b) => (a.posting_time < b.posting_time ? -1 : 1))[0];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-xl font-extrabold">排期日历</h1>
        <span className="font-mono text-xs text-dim">
          日更 {daily.length} 条 · 已采纳 {approved} · 种子 {all.length - daily.length}
          {next && ` · 下一条 ${next.handle} @ ${next.posting_time?.slice(5)}`}
        </span>
        <div className="flex-1" />
        <button onClick={genDaily} disabled={genning}
          className="rounded-lg border border-lime bg-lime/[.08] px-3 py-[6px] font-mono text-xs text-lime hover:bg-lime/[.16] disabled:opacity-50">
          {genning ? "已启动…" : "⚡ 生成今日16条"}
        </button>
        <button onClick={() => sched.reload()} className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text">刷新</button>
      </div>

      <TrendsPanel />

      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
        <select value={fAccount} onChange={(e) => setFAccount(e.target.value)} className="rounded border border-line bg-transparent px-2 py-1 text-muted">
          <option value="all">全部账号</option>
          {handles.map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
        {(["all", "daily", "seed"] as const).map((t) => (
          <button key={t} onClick={() => setFType(t)}
            className={`rounded px-2.5 py-1 ${fType === t ? "bg-lime/[.12] text-lime" : "text-dim hover:text-text"}`}>
            {t === "all" ? "全部" : t === "daily" ? "日更" : "种子"}
          </button>
        ))}
        <span className="text-dim">共 {items.length} 条</span>
      </div>

      {msg && <div className="rounded-lg border border-lime/40 bg-lime/[.08] px-3 py-2 font-mono text-xs text-lime">{msg}</div>}
      {sched.loading && !all.length && <div className="font-mono text-sm text-dim">加载中…</div>}
      {!sched.loading && !items.length && (
        <div className="rounded-lg border border-line px-4 py-8 text-center font-mono text-sm text-dim">
          没有匹配的内容。点右上「⚡ 生成今日16条」跑一轮自驾。
        </div>
      )}

      {groups.map(([date, list]) => (
        <section key={date} className="space-y-3">
          <div className="flex items-center gap-2 border-b border-line pb-1">
            <span className="font-display text-base font-bold">{date}</span>
            <span className="font-mono text-[11px] text-dim">{list.length} 条</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {list.map((it) => <Card key={it.asset_id} it={it} onAct={act} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
