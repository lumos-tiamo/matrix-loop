import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { DraftOut, VideoAssetOut } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok", twitter: "X",
  weixin_video: "视频号", weixin_gzh: "公众号", youtube: "YouTube", instagram: "IG", bilibili: "B站",
};

export function Video() {
  const accounts = useAsync(() => api.listAccounts(), []);
  const usage = useAsync(() => api.getVideoUsage(), []);
  const [acctId, setAcctId] = useState<number | "">("");
  const [genNonce, setGenNonce] = useState(0);

  const u = usage.data;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">
            视频<span className="text-violet">工作台</span>
          </h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">
            定调 → 选题 → 脚本 → 视频 → <span className="text-warn">人审成片</span> → 发布 · 每一步人在环
          </p>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 font-mono text-xs text-muted">
          选择账号
          <select
            aria-label="选择账号"
            className="rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text focus:border-violet focus:outline-none"
            value={acctId}
            onChange={(e) => setAcctId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">选择账号…</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {(PLATFORM_LABEL[a.platform] ?? a.platform)} · {a.handle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* usage panel */}
      <ChartCard title="📊 视频用量" pill={u ? `预算 ${u.caps.video_budget}` : "—"} className="mb-[14px]">
        <div className="grid grid-cols-2 gap-[14px] md:grid-cols-4">
          <StatTile label="今日条数" value={String(u?.today_count ?? 0)} accent />
          <StatTile label="今日成本" value={String((u?.today_cost ?? 0).toFixed(2))} />
          <StatTile label="累计条数" value={String(u?.total_count ?? 0)} />
          <StatTile label="累计成本" value={String((u?.total_cost ?? 0).toFixed(2))} />
        </div>
        <p className="mt-[10px] font-mono text-[10px] leading-relaxed text-dim">
          日上限:全局 {u?.caps.max_videos_per_day ?? "—"} · 单号 {u?.caps.per_account_per_day ?? "—"} · 单垂类 {u?.caps.per_channel_per_day ?? "—"}
        </p>
      </ChartCard>

      {acctId === "" ? (
        <ChartCard title="👆 先选一个账号">
          <p className="py-8 text-center font-mono text-xs text-muted">选择账号后可设定调、生成脚本/视频、审核成片。</p>
        </ChartCard>
      ) : (
        <div className="grid gap-[14px] lg:grid-cols-2">
          <BriefEditor accountId={acctId} />
          <DraftWorkflow accountId={acctId} onGenerated={() => { usage.reload(); setGenNonce((n) => n + 1); }} />
          <ReviewQueue accountId={acctId} genNonce={genNonce} className="lg:col-span-2" />
        </div>
      )}
    </div>
  );
}

// Placeholder sub-components — implemented in Tasks 3-5.
function BriefEditor({ accountId }: { accountId: number }) {
  const brief = useAsync(
    () => api.getBrief(accountId).catch((e: Error & { status?: number }) => {
      if (e.status === 404) return null;
      throw e;
    }),
    [accountId],
  );
  const [main, setMain] = useState("");
  const [niches, setNiches] = useState("");
  const [tone, setTone] = useState("");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState("en");
  const [format, setFormat] = useState("faceless");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // hydrate the form once the brief for this account arrives
  useEffect(() => {
    if (brief.loading) return;
    const b = brief.data;
    setMain(b?.main_direction ?? "");
    setNiches((b?.sub_niches ?? []).join("、"));
    setTone(b?.tone ?? "");
    setPersona(b?.persona ?? "");
    setLanguage(b?.language ?? "en");
    setFormat(b?.format ?? "faceless");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, brief.loading]);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      await api.setBrief(accountId, {
        main_direction: main.trim(),
        sub_niches: niches.split(/[、,，]/).map((s) => s.trim()).filter(Boolean),
        tone: tone.trim() || null,
        persona: persona.trim() || null,
        language,
        format,
      });
      setMsg("已保存定调");
      brief.reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  const inputCls = "w-full rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text placeholder:text-muted focus:border-violet focus:outline-none";

  return (
    <ChartCard title="🎯 频道定调">
      <div className="space-y-[10px]">
        {brief.error && <p className="mb-2 font-mono text-[11px] text-alert">定调加载失败：{brief.error}</p>}
        <input aria-label="主方向" className={inputCls} placeholder="主方向,如 web3" value={main} onChange={(e) => setMain(e.target.value)} />
        <input aria-label="子垂类" className={inputCls} placeholder="子垂类(顿号分隔),如 加密交易者、空投猎人、DeFi" value={niches} onChange={(e) => setNiches(e.target.value)} />
        <div className="flex gap-2">
          <input aria-label="人设" className={inputCls} placeholder="人设,如 Nina" value={persona} onChange={(e) => setPersona(e.target.value)} />
          <input aria-label="语气" className={inputCls} placeholder="语气,如 punchy" value={tone} onChange={(e) => setTone(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <select aria-label="语言" className={inputCls} value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
          <select aria-label="形态" className={inputCls} value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="faceless">faceless 口播</option>
            <option value="avatar">数字人</option>
          </select>
        </div>
        <button
          onClick={save}
          disabled={busy}
          className="rounded-lg border border-violet/50 bg-violet/[.1] px-4 py-2 font-mono text-xs text-violet transition-colors hover:bg-violet/[.18] disabled:opacity-50"
        >
          {busy ? "保存中…" : "保存定调"}
        </button>
        {msg && <p className="font-mono text-[11px] text-muted">{msg}</p>}
      </div>
    </ChartCard>
  );
}
function DraftWorkflow({ accountId, onGenerated }: { accountId: number; onGenerated: () => void }) {
  const detail = useAsync(() => api.getAccount(accountId), [accountId]);
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [isErr, setIsErr] = useState(false);

  const drafts: DraftOut[] = useMemo(() => {
    const runs = detail.data?.loop_runs ?? [];
    const all = runs.flatMap((r) => r.drafts ?? []);
    return [...all].reverse();   // newest first
  }, [detail.data]);

  async function act(key: number, fn: () => Promise<unknown>, done: string) {
    setBusy(key);
    try { await fn(); setIsErr(false); setMsg(done); detail.reload(); onGenerated(); }
    catch (e) { setIsErr(true); setMsg(String(e)); }
    finally { setBusy(null); }
  }

  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <ChartCard title="✍️ 选题 · 脚本 · 视频" pill={`${drafts.length} 草稿`}>
      {drafts.length === 0 && (
        <p className="py-6 text-center font-mono text-[11px] text-muted">
          还没有草稿。先在总览/下钻里对该账号跑一轮 Loop 生成选题。
        </p>
      )}
      <div className="space-y-[8px]">
        {drafts.map((d) => {
          const adopted = d.review_status === "adopted";
          return (
            <div key={d.id} className="rounded-lg border border-line bg-panel px-3 py-2">
              <div className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
                <span className={d.kind === "script" ? "text-cyan" : "text-lime"}>{d.kind}</span>
                <span className="text-dim">#{d.id}</span>
                <span className="text-muted">{d.review_status}</span>
              </div>
              <p className="mb-2 font-mono text-[11px] leading-relaxed text-text">{d.content.slice(0, 200)}</p>
              <div className="flex gap-2">
                {!adopted && (
                  <button className={`${btn} border-muted/40 text-muted hover:text-text`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.setDraftStatus(d.id, "adopted"), "已采纳")}>
                    采纳{d.kind === "script" ? "脚本" : "选题"}
                  </button>
                )}
                {adopted && d.kind === "topic" && (
                  <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.generateScript(d.id), "已生成脚本")}>
                    {busy === d.id ? "生成中…" : "生成脚本"}
                  </button>
                )}
                {adopted && d.kind === "script" && (
                  <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`} disabled={busy === d.id}
                    onClick={() => act(d.id, () => api.generateVideo(accountId, d.id), "已生成视频")}>
                    {busy === d.id ? "生成中…" : "生成视频"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {msg && <p className={isErr ? "mt-2 font-mono text-[11px] text-alert" : "mt-2 font-mono text-[11px] text-muted"}>{msg}</p>}
    </ChartCard>
  );
}
function ReviewQueue({ accountId, genNonce, className }: { accountId: number; genNonce: number; className?: string }) {
  const assets = useAsync(() => api.listVideoAssets({ account_id: accountId }), [accountId, genNonce]);
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function review(id: number, status: string) {
    setBusy(id);
    try { await api.setVideoReview(id, status); assets.reload(); }
    catch (e) { setMsg(String(e)); }
    finally { setBusy(null); }
  }

  const rows: VideoAssetOut[] = assets.data ?? [];
  const badge: Record<string, string> = {
    pending: "text-warn", approved: "text-good", rejected: "text-alert",
  };
  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <ChartCard title="🎬 成片审核" pill={`${rows.length} 条`} className={className}>
      {rows.length === 0 && (
        <p className="py-6 text-center font-mono text-[11px] text-muted">该账号还没有成片。生成后在这里审核。</p>
      )}
      <div className="space-y-[8px]">
        {rows.map((v) => (
          <div key={v.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel px-3 py-2">
            <span className="font-mono text-[11px] text-dim">#{v.id}</span>
            <span className="font-mono text-[11px] text-muted">{v.provider}</span>
            <span className={`font-mono text-[11px] ${badge[v.review_status] ?? "text-muted"}`}>{v.review_status}</span>
            <span className="font-mono text-[10px] text-dim">成本 {v.cost}</span>
            {v.media_url && /^https?:\/\//.test(v.media_url) && (
              <a href={v.media_url} target="_blank" rel="noreferrer"
                className="font-mono text-[11px] text-cyan underline decoration-dotted hover:text-cyan/80">看成片</a>
            )}
            <div className="flex-1" />
            {v.review_status === "pending" && (
              <>
                <button className={`${btn} border-good/50 bg-good/[.08] text-good`} disabled={busy === v.id}
                  onClick={() => review(v.id, "approved")}>通过</button>
                <button className={`${btn} border-alert/50 bg-alert/[.08] text-alert`} disabled={busy === v.id}
                  onClick={() => review(v.id, "rejected")}>否决</button>
              </>
            )}
          </div>
        ))}
      </div>
      {msg && <p className="mt-2 font-mono text-[11px] text-alert">{msg}</p>}
    </ChartCard>
  );
}
