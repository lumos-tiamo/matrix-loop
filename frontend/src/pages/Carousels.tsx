import { useState } from "react";
import { api, mediaSrc } from "../api/client";
import { useAsync } from "../api/hooks";
import type { CarouselItem } from "../api/types";

const BRAND: Record<string, string> = { AE: "#8B5CFF", CC: "#38BDF8", QY: "#F5B301", AU: "#C6FF3A" };

export function Carousels() {
  const cs = useAsync(() => api.getCarousels(), [], 15000);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const items = cs.data ?? [];

  async function gen() {
    setBusy(true); setMsg(null);
    try {
      await api.generateCarousels();
      setMsg("已启动生成 4 个账号的图文(真数据·无AI假图)。约 1–2 分钟后出现在下方,自动刷新。");
    } catch (e) { setMsg(String(e)); }
    finally { setTimeout(() => setBusy(false), 3000); }
  }

  function downloadAll(c: CarouselItem) {
    c.slide_urls.forEach((u, i) => {
      const a = document.createElement("a");
      a.href = mediaSrc(u) || u; a.download = `${c.folder}_${i + 1}.png`;
      document.body.appendChild(a); a.click(); a.remove();
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-xl font-extrabold">图文</h1>
        <span className="font-mono text-xs text-dim">IG carousel「N 图讲清」· 真数据真图 · 零 AI 假图 · 共 {items.length} 组</span>
        <div className="flex-1" />
        <button onClick={gen} disabled={busy}
          className="rounded-lg border border-lime bg-lime/[.12] px-3 py-[6px] font-mono text-xs font-bold text-lime hover:bg-lime/[.2] disabled:opacity-50">
          {busy ? "已启动…" : "🖼 生成今日图文(4账号)"}
        </button>
        <button onClick={() => cs.reload()} className="rounded-lg border border-line px-3 py-[6px] font-mono text-xs text-muted hover:text-text">刷新</button>
      </div>

      {msg && <div className="rounded-lg border border-lime/40 bg-lime/[.08] px-3 py-2 font-mono text-xs text-lime">{msg}</div>}
      {cs.loading && !items.length && <div className="font-mono text-sm text-dim">加载中…</div>}
      {!cs.loading && !items.length && (
        <div className="rounded-lg border border-line px-4 py-8 text-center font-mono text-sm text-dim">
          还没有图文。点右上「🖼 生成今日图文」——后端会用已核实热点+真数据出多图 carousel。
        </div>
      )}

      <div className="space-y-6">
        {items.map((c) => (
          <section key={c.folder} className="glass p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold text-black"
                style={{ background: BRAND[c.brand ?? ""] ?? "#8B5CFF" }}>{c.handle || c.brand}</span>
              <span className="font-mono text-[11px] text-dim">{c.date} · {c.slide_urls.length} 图</span>
              {c.source && <a href={c.source} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-sky-400 hover:underline">来源↗</a>}
              <span className="flex-1" />
              <button onClick={() => downloadAll(c)} className="rounded border border-line px-2 py-0.5 font-mono text-[11px] text-muted hover:border-lime hover:text-lime">下载全部</button>
            </div>
            {c.topic && <p className="mb-2 line-clamp-1 text-xs text-muted">{c.topic}</p>}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {c.slide_urls.map((u, i) => (
                <a key={i} href={mediaSrc(u) || u} target="_blank" rel="noreferrer" className="shrink-0">
                  <img src={mediaSrc(u) || u} alt={`slide ${i + 1}`} loading="lazy"
                    className="h-72 w-auto thumb-card" />
                </a>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
