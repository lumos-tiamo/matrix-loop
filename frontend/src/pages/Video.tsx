import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
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
          <StatTile label="今日成本" value={String(u?.today_cost ?? 0)} />
          <StatTile label="累计条数" value={String(u?.total_count ?? 0)} />
          <StatTile label="累计成本" value={String(u?.total_cost ?? 0)} />
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
          <DraftWorkflow accountId={acctId} onGenerated={() => usage.reload()} />
          <ReviewQueue accountId={acctId} className="lg:col-span-2" />
        </div>
      )}
    </div>
  );
}

// Placeholder sub-components — implemented in Tasks 3-5.
function BriefEditor({ accountId }: { accountId: number }) {
  const brief = useAsync(() => api.getBrief(accountId).catch(() => null), [accountId]);
  const [main, setMain] = useState("");
  const [niches, setNiches] = useState("");
  const [tone, setTone] = useState("");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState("en");
  const [format, setFormat] = useState("faceless");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadedFor, setLoadedFor] = useState<number | null>(null);

  // hydrate the form once the brief for this account arrives
  if (!brief.loading && loadedFor !== accountId) {
    const b = brief.data;
    setMain(b?.main_direction ?? "");
    setNiches((b?.sub_niches ?? []).join("、"));
    setTone(b?.tone ?? "");
    setPersona(b?.persona ?? "");
    setLanguage(b?.language ?? "en");
    setFormat(b?.format ?? "faceless");
    setLoadedFor(accountId);
  }

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
        <input className={inputCls} placeholder="主方向,如 web3" value={main} onChange={(e) => setMain(e.target.value)} />
        <input className={inputCls} placeholder="子垂类(顿号分隔),如 加密交易者、空投猎人、DeFi" value={niches} onChange={(e) => setNiches(e.target.value)} />
        <div className="flex gap-2">
          <input className={inputCls} placeholder="人设,如 Nina" value={persona} onChange={(e) => setPersona(e.target.value)} />
          <input className={inputCls} placeholder="语气,如 punchy" value={tone} onChange={(e) => setTone(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <select className={inputCls} value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
          <select className={inputCls} value={format} onChange={(e) => setFormat(e.target.value)}>
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
  void accountId; void onGenerated;
  return <ChartCard title="✍️ 选题 · 脚本 · 视频"><div data-testid="draft-workflow" /></ChartCard>;
}
function ReviewQueue({ accountId, className }: { accountId: number; className?: string }) {
  void accountId;
  return <ChartCard title="🎬 成片审核" className={className}><div data-testid="review-queue" /></ChartCard>;
}
