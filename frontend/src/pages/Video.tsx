import { useEffect, useMemo, useState } from "react";
import { api, mediaSrc } from "../api/client";
import { useAsync } from "../api/hooks";
import type { DraftOut, VideoAssetOut, PublishDispatchOut } from "../api/types";
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
        <div className="grid gap-[14px]">
          <BriefEditor accountId={acctId} />
          <Workbench accountId={acctId} onChange={() => usage.reload()} />
        </div>
      )}
    </div>
  );
}

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
  const [targetSeconds, setTargetSeconds] = useState(50);
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
    setTargetSeconds(b?.target_seconds ?? 50);
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
        target_seconds: targetSeconds,
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
        <input aria-label="视频时长" type="number" min={15} max={180} className={inputCls}
          placeholder="视频时长(秒)" value={targetSeconds}
          onChange={(e) => setTargetSeconds(Number(e.target.value) || 50)} />
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

function GenProgress({ createdAt, now, stage, progress }: {
  createdAt: string; now: number; stage?: string | null; progress?: number;
}) {
  const elapsed = Math.max(0, now - new Date(createdAt).getTime());
  const mm = Math.floor(elapsed / 60000);
  const ss = String(Math.floor((elapsed % 60000) / 1000)).padStart(2, "0");
  const pct = Math.max(0, Math.min(100, progress ?? 0));   // REAL backend progress
  const started = pct > 0 || !!stage;                       // before first real update: indeterminate
  return (
    <div className="mt-[6px] w-full">
      <div className="mb-[3px] flex justify-between font-mono text-[10px] text-muted">
        <span className="text-warn">{stage ? `⚙ ${stage}` : "排队中…"}</span>
        <span>{started ? `${pct}% · ` : ""}{mm}:{ss}</span>
      </div>
      <div className="h-[6px] w-full overflow-hidden rounded-full bg-line">
        {started ? (
          <div className="h-full rounded-full bg-gradient-to-r from-violet to-cyan transition-[width] duration-700 ease-out"
            style={{ width: `${Math.max(3, pct)}%` }} />
        ) : (
          // no real signal yet → honest indeterminate shimmer, not a fake fill
          <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-violet to-cyan" />
        )}
      </div>
    </div>
  );
}

// ---- pipeline stage label for a topic's card header ----------------------------------------
function pipelineStage(hasScript: boolean, scriptAdopted: boolean, asset?: VideoAssetOut) {
  if (!hasScript) return { label: "① 待脚本", tone: "text-lime" };
  if (!scriptAdopted) return { label: "② 待采纳", tone: "text-cyan" };
  if (!asset) return { label: "③ 待出片", tone: "text-violet" };
  if (asset.status === "generating") return { label: `④ 渲染中 ${asset.progress ?? 0}%`, tone: "text-warn" };
  if (asset.status === "failed") return { label: "✖ 失败", tone: "text-alert" };
  if (asset.review_status === "approved") return { label: "✅ 已通过", tone: "text-good" };
  if (asset.review_status === "rejected") return { label: "⊘ 已否决", tone: "text-alert" };
  return { label: "⑤ 待审核", tone: "text-warn" };
}

// ---- 6-step pipeline tracker shown at the top of every card -------------------------------
const PIPE_STEPS = ["采纳选题", "生成脚本", "采纳脚本", "生成视频", "剪辑精修", "发布配套"];
function StepTracker({ hasScript, scriptAdopted, asset, published }: {
  hasScript: boolean; scriptAdopted: boolean; asset?: VideoAssetOut; published?: boolean;
}) {
  const reached = [
    true,                                                                              // ① 采纳选题(卡片存在即已有选题)
    hasScript,                                                                          // ② 生成脚本
    scriptAdopted,                                                                      // ③ 采纳脚本
    !!asset && ["ready", "failed"].includes(asset.status) || asset?.review_status === "approved", // ④ 生成视频
    !!asset && ((asset.provider || "").includes("palmier") || asset.stage === "palmier_queued" || asset.stage === "palmier_done"), // ⑤ 剪辑精修
    !!published,                                                                        // ⑥ 发布配套/已排期
  ];
  let current = reached.findIndex((r) => !r);
  if (current === -1) current = reached.length - 1;
  return (
    <div className="flex flex-wrap items-center gap-[3px]">
      {PIPE_STEPS.map((label, i) => (
        <span key={i}
          className={`rounded px-[5px] py-[1px] font-mono text-[9px] ${
            i === current ? "bg-violet/[.2] text-violet"
              : reached[i] ? "bg-cyan/[.12] text-cyan"
              : "bg-line/60 text-dim"}`}>
          {i + 1} {label}
        </span>
      ))}
    </div>
  );
}

const SLOT_LABEL: Record<string, string> = {
  first_reply: "X · 外链放首条回复", link_sticker_bio: "IG · link sticker + bio", bio: "bio 链接",
};

/** Step-6: edit the platform-native publishing companion content (caption/标签/外链槽/发布时间),
 *  then 发布/排期 (which uses the saved plan). Only shown for approved assets. */
function PublishPanel({ asset, accountId, platform, dispatch, run }: {
  asset: VideoAssetOut; accountId: number; platform?: string;
  dispatch?: PublishDispatchOut; run: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const defaultSlot = platform === "twitter" ? "first_reply" : platform === "instagram" ? "link_sticker_bio" : "bio";
  const plan = useAsync(
    () => api.getPublishPlan(asset.id).catch((e: Error & { status?: number }) => {
      if (e.status === 404) return null;
      throw e;
    }),
    [asset.id],
  );
  const [caption, setCaption] = useState("");
  const [tags, setTags] = useState("");
  const [slot, setSlot] = useState(defaultSlot);
  const [linkText, setLinkText] = useState("");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (plan.loading) return;
    const p = plan.data;
    setCaption(p?.caption ?? "");
    setTags((p?.hashtags ?? []).join(" "));
    setSlot(p?.external_link_slot ?? defaultSlot);
    setLinkText(p?.external_link_text ?? "");
    setWhen(p?.posting_time ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset.id, plan.loading]);

  async function save(status: string) {
    setBusy(true); setMsg(null);
    try {
      await api.putPublishPlan(asset.id, {
        caption: caption.trim() || null,
        hashtags: tags.split(/[\s,，]+/).map((s) => s.trim()).filter(Boolean),
        external_link_slot: slot,
        external_link_text: linkText.trim() || null,
        posting_time: when.trim() || null,
        status,
      });
      setMsg(status === "ready" ? "✓ 已标记就绪" : "✓ 已保存草稿");
      plan.reload();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }

  const inp = "w-full rounded-[7px] border border-line bg-bg px-[8px] py-[5px] font-mono text-[11px] text-text placeholder:text-dim focus:border-violet focus:outline-none";
  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <div className="mt-2 rounded-md border border-violet/30 bg-violet/[.04] p-[10px]">
      <div className="mb-[6px] font-mono text-[10px] uppercase tracking-wider text-violet">发布配套内容 · step 6</div>
      <div className="space-y-[6px]">
        <textarea aria-label="平台文案" className={`${inp} min-h-[64px] resize-y`} placeholder="平台正文文案(平台原生口吻)"
          value={caption} onChange={(e) => setCaption(e.target.value)} />
        <input aria-label="话题标签" className={inp} placeholder="话题标签(空格分隔,如 #airdrop #defi)"
          value={tags} onChange={(e) => setTags(e.target.value)} />
        <div className="flex gap-2">
          <select aria-label="外链位置" className={inp} value={slot} onChange={(e) => setSlot(e.target.value)}>
            <option value="first_reply">X · 首条回复</option>
            <option value="link_sticker_bio">IG · link sticker + bio</option>
            <option value="bio">bio 链接(未满1000粉)</option>
          </select>
          <input aria-label="发布时间" className={inp} placeholder="发布时间,如 台湾 20:00"
            value={when} onChange={(e) => setWhen(e.target.value)} />
        </div>
        <input aria-label="外链引流话术" className={inp} placeholder={`外链引流话术(${SLOT_LABEL[slot] ?? slot})`}
          value={linkText} onChange={(e) => setLinkText(e.target.value)} />
        <div className="flex flex-wrap items-center gap-2 pt-[2px]">
          <button className={`${btn} border-muted/40 text-muted hover:text-text`} disabled={busy}
            onClick={() => save("draft")}>{busy ? "…" : "存草稿"}</button>
          <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy}
            onClick={() => save("ready")}>标记就绪</button>
          <div className="flex-1" />
          {dispatch ? (
            <span className="font-mono text-[10px] text-good">
              ✓ 已{dispatch.status === "published" ? "发布" : "排期"}{dispatch.publish_at ? ` · ${dispatch.publish_at.slice(0, 16).replace("T", " ")}` : ""}
            </span>
          ) : (
            <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`} disabled={busy}
              title="用上面保存的配套内容发布/排期(未配 AiToEarn 会诚实报错)"
              onClick={() => run(() => api.publish(accountId, asset.id))}>发布 / 排期 →</button>
          )}
        </div>
        {plan.data?.status === "ready" && !dispatch && (
          <p className="font-mono text-[10px] text-good">配套内容已就绪,可发布</p>
        )}
        {msg && <p className="font-mono text-[10px] text-muted">{msg}</p>}
      </div>
    </div>
  );
}

const GEN_POLL_MS = 4000;

/** Video workbench — two lists of collapsible pipeline cards (Seedance/RunningHub job-card style):
 *  选题池 = recommendations to adopt; 制作中 = adopted topics, each card holding its whole
 *  pipeline (选题 → 脚本 → 视频). Adopting moves a card between lists; generating a script/video
 *  updates the SAME card in place — nothing jumps to the bottom. */
function Workbench({ accountId, onChange }: { accountId: number; onChange: () => void }) {
  const detail = useAsync(() => api.getAccount(accountId), [accountId]);
  const assetsQ = useAsync(() => api.listVideoAssets({ account_id: accountId }), [accountId]);
  const dispatchesQ = useAsync(() => api.listDispatches(accountId), [accountId]);
  const [now, setNow] = useState(() => Date.now());
  const [msg, setMsg] = useState<string | null>(null);

  const assets: VideoAssetOut[] = useMemo(() => assetsQ.data ?? [], [assetsQ.data]);
  const platform = detail.data?.platform;
  const hasGenerating = assets.some((a) => a.status === "generating");
  const hasPalmierQueued = assets.some((a) => a.stage === "palmier_queued");
  // dispatch by video_asset_id (non-failed = published/queued) → drives step-6 "已发布" state
  const dispatchByAsset = useMemo(() => {
    const m = new Map<number, PublishDispatchOut>();
    const rows = Array.isArray(dispatchesQ.data) ? dispatchesQ.data : [];
    for (const d of rows) {
      if (d.video_asset_id != null && d.status !== "failed" && !m.has(d.video_asset_id)) {
        m.set(d.video_asset_id, d);
      }
    }
    return m;
  }, [dispatchesQ.data]);

  // live poll (asset progress + script landing + palmier finishing) while anything is in flight
  useEffect(() => {
    if (!hasGenerating && !hasPalmierQueued) return;
    const tick = setInterval(() => setNow(Date.now()), 1000);
    const poll = setInterval(() => { assetsQ.reload(); detail.reload(); dispatchesQ.reload(); }, GEN_POLL_MS);
    return () => { clearInterval(tick); clearInterval(poll); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasGenerating, hasPalmierQueued]);

  const { topics, scriptByTopic, assetByScript } = useMemo(() => {
    const runs = detail.data?.loop_runs ?? [];
    const all = runs.flatMap((r) => r.drafts ?? []);
    const topics = all.filter((d) => d.kind === "topic");
    const scriptByTopic = new Map<number, DraftOut>();
    for (const s of all) {
      if (s.kind === "script" && s.parent_id != null) {
        const cur = scriptByTopic.get(s.parent_id);
        if (!cur || s.id > cur.id) scriptByTopic.set(s.parent_id, s);   // latest script per topic
      }
    }
    const assetByScript = new Map<number, VideoAssetOut>();
    for (const a of assets) {
      if (a.script_draft_id != null) {
        const cur = assetByScript.get(a.script_draft_id);
        if (!cur || a.id > cur.id) assetByScript.set(a.script_draft_id, a);  // latest asset per script
      }
    }
    return { topics, scriptByTopic, assetByScript };
  }, [detail.data, assets]);

  // stable sort (newest topic first); status changes never reorder within a list
  const pending = topics.filter((t) => t.review_status !== "adopted").slice().sort((a, b) => b.id - a.id);
  const inProd = topics.filter((t) => t.review_status === "adopted").slice().sort((a, b) => b.id - a.id);

  async function run(fn: () => Promise<unknown>) {
    setMsg(null);
    try { await fn(); detail.reload(); assetsQ.reload(); onChange(); }
    catch (e) { setMsg(String(e)); }
  }

  return (
    <div className="grid gap-[14px] lg:grid-cols-2">
      <ChartCard title="🔥 选题池" pill={`${pending.length}`}>
        {pending.length === 0 && (
          <p className="py-6 text-center font-mono text-[11px] text-muted">
            没有待处理选题。在总览/账号页点「⚡ 跑一轮」生成选题。
          </p>
        )}
        <div className="space-y-[8px]">
          {pending.map((t) => (
            <TopicCard key={t.id} topic={t} script={scriptByTopic.get(t.id)} asset={undefined}
              accountId={accountId} now={now} run={run} defaultOpen={false} platform={platform} />
          ))}
        </div>
      </ChartCard>

      <ChartCard title="🎬 制作中 · 成片" pill={hasGenerating ? "生成中…" : `${inProd.length}`}>
        {inProd.length === 0 && (
          <p className="py-6 text-center font-mono text-[11px] text-muted">
            采纳选题后出现在这里。脚本、视频都收在各自卡片内,不会跳走。
          </p>
        )}
        <div className="space-y-[8px]">
          {inProd.map((t) => {
            const s = scriptByTopic.get(t.id);
            const a = s ? assetByScript.get(s.id) : undefined;
            return (
              <TopicCard key={t.id} topic={t} script={s} asset={a}
                accountId={accountId} now={now} run={run} defaultOpen
                platform={platform} dispatch={a ? dispatchByAsset.get(a.id) : undefined} />
            );
          })}
        </div>
      </ChartCard>
      {msg && <p className="font-mono text-[11px] text-alert lg:col-span-2">{msg}</p>}
    </div>
  );
}

/** One collapsible card = one topic's whole pipeline: 选题 → 脚本 → 视频(进度/预览/审核/发布). */
function TopicCard({ topic, script, asset, accountId, now, run, defaultOpen, platform, dispatch }: {
  topic: DraftOut; script?: DraftOut; asset?: VideoAssetOut; accountId: number; now: number;
  run: (fn: () => Promise<unknown>) => Promise<void>; defaultOpen: boolean;
  platform?: string; dispatch?: PublishDispatchOut;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState(false);
  const adopted = topic.review_status === "adopted";
  const scriptAdopted = script?.review_status === "adopted";
  const stage = pipelineStage(!!script, !!scriptAdopted, asset);
  const src = mediaSrc(asset?.media_url);
  const title = (topic.content.split("\n")[0] || topic.content).slice(0, 46);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try { await run(fn); } finally { setBusy(false); }
  }
  const btn = "rounded-md border px-[10px] py-[4px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <div className="rounded-lg border border-line bg-panel">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        <span className="font-mono text-[10px] text-dim">{open ? "▾" : "▸"}</span>
        {!adopted && topic.review_status === "pending" && (
          <span className="shrink-0 rounded bg-warn/[.15] px-[5px] py-[1px] font-mono text-[10px] text-warn">🔥</span>
        )}
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-text">{title}</span>
        <span className={`shrink-0 font-mono text-[10px] ${stage.tone}`}>{stage.label}</span>
      </button>

      {open && (
        <div className="space-y-[10px] border-t border-line px-3 py-[10px]">
          {/* 6 步流水线进度 */}
          <StepTracker hasScript={!!script} scriptAdopted={!!scriptAdopted} asset={asset} published={!!dispatch} />
          {/* 选题 */}
          <div>
            <div className="mb-[3px] font-mono text-[10px] uppercase tracking-wider text-dim">选题 · #{topic.id}</div>
            <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text">{topic.content}</p>
            {!adopted && (
              <button className={`${btn} mt-2 border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy}
                onClick={() => act(() => api.setDraftStatus(topic.id, "adopted"))}>
                {busy ? "…" : "采纳选题 → 进制作"}
              </button>
            )}
          </div>

          {/* 脚本 (adopted topics only) */}
          {adopted && (
            <div className="border-t border-line/60 pt-[10px]">
              <div className="mb-[3px] font-mono text-[10px] uppercase tracking-wider text-dim">脚本</div>
              {!script ? (
                <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy}
                  onClick={() => act(() => api.generateScript(topic.id))}>
                  {busy ? "生成中…" : "① 生成脚本"}
                </button>
              ) : (
                <>
                  <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text">{script.content}</p>
                  {!scriptAdopted ? (
                    <div className="mt-2 flex gap-2">
                      <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`} disabled={busy}
                        onClick={() => act(() => api.setDraftStatus(script.id, "adopted"))}>采纳脚本 →</button>
                      <button className={`${btn} border-muted/40 text-muted hover:text-text`} disabled={busy}
                        onClick={() => act(() => api.generateScript(topic.id))}>{busy ? "…" : "重写"}</button>
                    </div>
                  ) : (
                    <div className="mt-1 font-mono text-[10px] text-good">✓ 脚本已采纳</div>
                  )}
                </>
              )}
            </div>
          )}

          {/* 视频 (adopted script only) */}
          {scriptAdopted && script && (
            <div className="border-t border-line/60 pt-[10px]">
              <div className="mb-[3px] font-mono text-[10px] uppercase tracking-wider text-dim">视频</div>
              {!asset && (
                <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`} disabled={busy}
                  onClick={() => act(() => api.generateVideo(accountId, script.id))}>
                  {busy ? "提交中…" : "② 生成视频"}
                </button>
              )}
              {asset?.status === "generating" && (
                <GenProgress createdAt={asset.created_at} now={now} stage={asset.stage} progress={asset.progress} />
              )}
              {asset?.status === "generating" && (asset.progress ?? 0) === 0 &&
                now - new Date(asset.created_at).getTime() > 240000 && (
                <div className="mt-1 flex items-center gap-2">
                  <span className="font-mono text-[10px] text-alert">⚠ 疑似卡住(4min 无进度)</span>
                  <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet`} disabled={busy}
                    onClick={() => act(() => api.generateVideo(accountId, script.id))}>重试</button>
                </div>
              )}
              {asset?.status === "failed" && (
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-alert">生成失败</span>
                  <button className={`${btn} border-violet/50 bg-violet/[.1] text-violet`} disabled={busy}
                    onClick={() => act(() => api.generateVideo(accountId, script.id))}>重试</button>
                </div>
              )}
              {asset && asset.status === "ready" && (
                <div className="space-y-2">
                  {src && (
                    <video controls preload="metadata" src={src}
                      className="w-full max-w-[240px] rounded-md border border-line bg-black" />
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`font-mono text-[10px] ${asset.review_status === "approved" ? "text-good" : asset.review_status === "rejected" ? "text-alert" : "text-warn"}`}>
                      {asset.review_status}
                    </span>
                    <span className="font-mono text-[10px] text-dim">成本 {asset.cost}</span>
                    {src && (
                      <a href={src} target="_blank" rel="noreferrer"
                        className="font-mono text-[10px] text-cyan underline decoration-dotted">新窗口</a>
                    )}
                    <div className="flex-1" />
                    {/* Palmier finishing: queue for the scheduled agent, or show state */}
                    {(asset.provider || "").includes("palmier") ? (
                      <span className="font-mono text-[10px] text-good">✓ 已精修</span>
                    ) : asset.stage === "palmier_queued" ? (
                      <span className="font-mono text-[10px] text-warn">⏳ 精修排队中</span>
                    ) : (
                      <button className={`${btn} border-cyan/50 bg-cyan/[.08] text-cyan`} disabled={busy}
                        title="排入 Palmier 精修队列(定时 agent 会自动加品牌/精修)"
                        onClick={() => act(() => api.queuePalmier(asset.id))}>🎬 送 Palmier 精修</button>
                    )}
                    {asset.review_status === "pending" && (
                      <>
                        <button className={`${btn} border-good/50 bg-good/[.08] text-good`} disabled={busy}
                          onClick={() => act(() => api.setVideoReview(asset.id, "approved"))}>通过</button>
                        <button className={`${btn} border-alert/50 bg-alert/[.08] text-alert`} disabled={busy}
                          onClick={() => act(() => api.setVideoReview(asset.id, "rejected"))}>否决</button>
                      </>
                    )}
                  </div>
                  {/* step 6 · 发布配套内容(仅审核通过后) */}
                  {asset.review_status === "approved" && (
                    <PublishPanel asset={asset} accountId={accountId} platform={platform} dispatch={dispatch} run={run} />
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
