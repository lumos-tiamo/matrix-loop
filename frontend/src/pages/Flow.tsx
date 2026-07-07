import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { AccountListItem, FlowData, SegmentOut, EndpointOut, CompositionItem } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";
import { SankeyChart } from "../components/SankeyChart";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok",
  twitter: "X", x: "X", weixin_video: "视频号", wechat_video: "视频号", bilibili: "B站",
};

function fmtNum(n: number): string {
  return n.toLocaleString("en-US");
}

function stripPrefix(name: string): { kind: string; label: string } {
  const i = name.indexOf(":");
  return i === -1 ? { kind: "", label: name } : { kind: name.slice(0, i), label: name.slice(i + 1) };
}

// Demo seed applied client-side (no backend reset route in scope). Idempotent-ish:
// createSegment/createEndpoint 409 on dup are swallowed; assignments overwrite.
const DEMO_SEGMENTS = ["crypto", "海外投资者", "宝妈", "打工人群"];
const DEMO_ENDPOINTS: [string, string][] = [
  ["Nina", "linktr.ee/nina"],
  ["xaue", "xaue.com"],
];
const DEMO_ASSIGN: Record<string, { endpoint: string | null; segs: [string, number][] }> = {
  "@money_talk": { endpoint: "Nina", segs: [["crypto", 0.6], ["海外投资者", 0.4]] },
  "@tech_daily": { endpoint: "xaue", segs: [["crypto", 0.5], ["打工人群", 0.5]] },
  "@beauty_lab": { endpoint: "xaue", segs: [["宝妈", 0.7], ["打工人群", 0.3]] },
  "@travel_vlog": { endpoint: null, segs: [["海外投资者", 0.4], ["打工人群", 0.6]] },
  "@fit_coach": { endpoint: null, segs: [["打工人群", 1.0]] },
};

export function Flow() {
  const flow = useAsync(() => api.getFlow(), []);
  const accounts = useAsync(() => api.listAccounts(), []);

  const data: FlowData = flow.data ?? { nodes: [], links: [] };

  const stats = useMemo(() => {
    const nodes = data.nodes;
    const acctCount = nodes.filter((n) => n.name.startsWith("acct:")).length;
    const segCount = nodes.filter((n) => n.name.startsWith("seg:")).length;
    const epCount = nodes.filter((n) => n.name.startsWith("ep:") && !n.name.endsWith("未定向")).length;
    const unrouted = data.links
      .filter((l) => l.target === "ep:未定向")
      .reduce((s, l) => s + l.value, 0);
    // total modeled flow = sum of account→segment edges (first hop)
    const total = data.links
      .filter((l) => l.source.startsWith("acct:"))
      .reduce((s, l) => s + l.value, 0);
    return { acctCount, segCount, epCount, total, unrouted };
  }, [data]);

  const hasFlow = data.nodes.length > 0;

  function reload() {
    flow.reload();
    accounts.reload();
  }

  return (
    <div>
      {/* header */}
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">
            导流 / 转化<span className="text-violet">流向</span>
          </h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">
            账号 → 人群 → 变现出口 · 流量宽度按<span className="text-warn">粉丝建模</span>，非真实转化
          </p>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2 font-mono text-[10px]">
          <span className="flex items-center gap-1 text-muted"><i className="inline-block h-2 w-2 rounded-sm bg-lime" />账号</span>
          <span className="flex items-center gap-1 text-muted"><i className="inline-block h-2 w-2 rounded-sm bg-cyan" />人群</span>
          <span className="flex items-center gap-1 text-muted"><i className="inline-block h-2 w-2 rounded-sm bg-violet" />出口</span>
        </div>
      </div>

      {flow.loading && <div className="px-1 font-mono text-muted">加载中…</div>}
      {flow.error && <div className="px-1 font-mono text-alert">加载失败：{flow.error}</div>}

      {/* summary stats */}
      {hasFlow && (
        <div className="mb-[14px] grid grid-cols-2 gap-[14px] md:grid-cols-4">
          <StatTile label="账号" value={fmtNum(stats.acctCount)} accent />
          <StatTile label="人群标签" value={fmtNum(stats.segCount)} />
          <StatTile label="变现出口" value={fmtNum(stats.epCount)} />
          <StatTile label="建模总流量" value={fmtNum(stats.total)} />
        </div>
      )}

      <div className="grid gap-[14px] lg:grid-cols-[1.9fr_1fr]">
        {/* sankey */}
        <ChartCard
          title="🌊 导流桑基"
          pill={hasFlow ? `未定向 ${fmtNum(stats.unrouted)}` : "空"}
          glow
          className="rise min-h-[560px]"
        >
          {hasFlow ? (
            <SankeyChart flow={data} height={520} />
          ) : (
            <EmptyState onReset={reload} accounts={accounts.data ?? []} />
          )}
        </ChartCard>

        {/* config */}
        <FlowConfig
          flow={data}
          accounts={accounts.data ?? []}
          onChanged={reload}
        />
      </div>
    </div>
  );
}

function EmptyState({ onReset, accounts }: { onReset: () => void; accounts: AccountListItem[] }) {
  const [busy, setBusy] = useState(false);
  async function reset() {
    setBusy(true);
    try {
      await seedDemo(accounts);
      onReset();
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex h-[480px] flex-col items-center justify-center gap-4 text-center">
      <div className="text-4xl opacity-60">🪢</div>
      <div>
        <p className="font-display text-sm font-bold text-text">还没有导流数据</p>
        <p className="mt-1 max-w-[320px] font-mono text-[11px] leading-relaxed text-muted">
          在右侧配置面板给账号建人群标签、选出口、设占比；或一键载入示例流向。
        </p>
      </div>
      <button
        onClick={reset}
        disabled={busy}
        className="rounded-lg border border-violet/50 bg-violet/[.1] px-4 py-2 font-mono text-xs text-violet transition-colors hover:bg-violet/[.18] disabled:opacity-50"
      >
        {busy ? "载入中…" : "↻ 重置为示例"}
      </button>
    </div>
  );
}

/** Best-effort client-side demo seed via the write APIs (no backend reset route in scope). */
async function seedDemo(accounts: AccountListItem[]): Promise<void> {
  const segIds = new Map<string, number>();
  const epIds = new Map<string, number>();

  for (const label of DEMO_SEGMENTS) {
    try {
      const s = await api.createSegment(label);
      segIds.set(label, s.id);
    } catch { /* likely 409 already-exists; resolved below from flow */ }
  }
  for (const [name, pattern] of DEMO_ENDPOINTS) {
    try {
      const e = await api.createEndpoint(name, pattern);
      epIds.set(name, e.id);
    } catch { /* 409 */ }
  }

  // Resolve any labels/endpoints that already existed (409) by re-reading /flow node ids is not
  // possible (flow has no ids). We can still assign the ones we just created; pre-existing ones
  // keep their prior wiring. Assign compositions for accounts we can fully resolve.
  const byHandle = new Map(accounts.map((a) => [a.handle, a]));
  for (const [handle, plan] of Object.entries(DEMO_ASSIGN)) {
    const acc = byHandle.get(handle);
    if (!acc) continue;
    const comp: CompositionItem[] = [];
    for (const [label, weight] of plan.segs) {
      const id = segIds.get(label);
      if (id != null) comp.push({ segment_id: id, weight });
    }
    if (comp.length) {
      try { await api.setComposition(acc.id, comp); } catch { /* ignore */ }
    }
    const epId = plan.endpoint ? epIds.get(plan.endpoint) ?? null : null;
    if (plan.endpoint == null || epId != null) {
      try { await api.setEndpoint(acc.id, epId); } catch { /* ignore */ }
    }
  }
}

function FlowConfig({
  flow, accounts, onChanged,
}: {
  flow: FlowData;
  accounts: AccountListItem[];
  onChanged: () => void;
}) {
  const [segLabel, setSegLabel] = useState("");
  const [epName, setEpName] = useState("");
  const [epPattern, setEpPattern] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  // Segments / endpoints created this session (with real ids) — the assignable pool.
  const [segments, setSegments] = useState<SegmentOut[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOut[]>([]);

  const [acctId, setAcctId] = useState<number | "">("");
  const [pickedSegs, setPickedSegs] = useState<Record<number, number>>({}); // segId -> weight
  const [pickedEp, setPickedEp] = useState<number | "">("");
  const [epTouched, setEpTouched] = useState(false); // true only when user explicitly changed the endpoint select

  // labels already live in the flow (context; may lack ids so not directly assignable)
  const flowSegLabels = useMemo(
    () => flow.nodes.filter((n) => n.name.startsWith("seg:")).map((n) => stripPrefix(n.name).label),
    [flow.nodes],
  );
  const flowEpLabels = useMemo(
    () => flow.nodes.filter((n) => n.name.startsWith("ep:")).map((n) => stripPrefix(n.name).label).filter((l) => l !== "未定向"),
    [flow.nodes],
  );

  async function withBusy(key: string, fn: () => Promise<void>) {
    setBusy(key); setMsg(null);
    try { await fn(); } catch (e) { setMsg(String(e)); } finally { setBusy(null); }
  }

  const addSegment = () =>
    withBusy("seg", async () => {
      const label = segLabel.trim();
      if (!label) return;
      const s = await api.createSegment(label);
      setSegments((prev) => [...prev.filter((p) => p.id !== s.id), s]);
      setSegLabel("");
      setMsg(`已建人群「${s.label}」`);
    });

  const addEndpoint = () =>
    withBusy("ep", async () => {
      const name = epName.trim();
      if (!name) return;
      const e = await api.createEndpoint(name, epPattern.trim() || undefined);
      setEndpoints((prev) => [...prev.filter((p) => p.id !== e.id), e]);
      setEpName(""); setEpPattern("");
      setMsg(`已建出口「${e.name}」`);
    });

  const toggleSeg = (id: number) =>
    setPickedSegs((prev) => {
      const next = { ...prev };
      if (id in next) delete next[id]; else next[id] = 1;
      return next;
    });

  const applyComposition = () =>
    withBusy("assign", async () => {
      if (acctId === "") { setMsg("先选账号"); return; }
      const comp: CompositionItem[] = Object.entries(pickedSegs).map(([id, w]) => ({
        segment_id: Number(id), weight: w,
      }));
      if (comp.length) await api.setComposition(acctId, comp);
      if (epTouched) await api.setEndpoint(acctId, pickedEp === "" ? null : pickedEp);
      setMsg("已保存账号导流配置");
      onChanged();
    });

  const runClassify = () =>
    withBusy("llm", async () => {
      if (acctId === "") { setMsg("先选账号"); return; }
      const r = await api.classifyAudience(acctId);
      setMsg(r.segments.length ? `LLM 归类：${r.segments.join("、")}` : "LLM 未匹配到人群");
      onChanged();
    });

  const resetDemo = () =>
    withBusy("reset", async () => {
      await seedDemo(accounts);
      setMsg("已重置为示例流向");
      onChanged();
    });

  const inputCls =
    "w-full rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text placeholder:text-muted focus:border-lime focus:outline-none";
  const btnCls =
    "shrink-0 rounded-lg border px-3 py-[7px] font-mono text-[11px] transition-colors disabled:opacity-50";

  return (
    <ChartCard title="⚙️ 导流配置" className="rise self-start" style={{ animationDelay: "80ms" }}>
      <div className="space-y-4">
        {/* create segment */}
        <section>
          <div className="mb-[6px] font-mono text-[10px] uppercase tracking-wider text-dim">新建人群标签</div>
          <div className="flex gap-2">
            <input className={inputCls} placeholder="新建人群标签，如 打工人群" value={segLabel}
              onChange={(e) => setSegLabel(e.target.value)} />
            <button className={`${btnCls} border-cyan/50 bg-cyan/[.08] text-cyan hover:bg-cyan/[.16]`}
              onClick={addSegment} disabled={busy === "seg"}>+ 加人群</button>
          </div>
        </section>

        {/* create endpoint */}
        <section>
          <div className="mb-[6px] font-mono text-[10px] uppercase tracking-wider text-dim">新建变现出口</div>
          <div className="flex gap-2">
            <input className={inputCls} placeholder="出口名，如 Nina" value={epName}
              onChange={(e) => setEpName(e.target.value)} />
            <input className={inputCls} placeholder="bio 外链子串(可选)" value={epPattern}
              onChange={(e) => setEpPattern(e.target.value)} />
            <button className={`${btnCls} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`}
              onClick={addEndpoint} disabled={busy === "ep"}>+ 加出口</button>
          </div>
        </section>

        <hr className="border-line" />

        {/* per-account assignment */}
        <section>
          <div className="mb-[6px] font-mono text-[10px] uppercase tracking-wider text-dim">给账号配置导流</div>
          <select
            className={`${inputCls} appearance-none`}
            value={acctId}
            onChange={(e) => { setAcctId(e.target.value === "" ? "" : Number(e.target.value)); setPickedSegs({}); setPickedEp(""); setEpTouched(false); }}
          >
            <option value="">选择账号…</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {(PLATFORM_LABEL[a.platform] ?? a.platform)} · {a.handle}
              </option>
            ))}
          </select>

          {/* pick segments (session-created pool) */}
          {segments.length > 0 && (
            <div className="mt-[10px]">
              <div className="mb-[5px] font-mono text-[10px] text-muted">人群占比</div>
              <div className="flex flex-wrap gap-[6px]">
                {segments.map((s) => {
                  const on = s.id in pickedSegs;
                  return (
                    <span key={s.id} className="flex items-center gap-1">
                      <button
                        onClick={() => toggleSeg(s.id)}
                        className={`rounded-full border px-[10px] py-[4px] font-mono text-[11px] ${
                          on ? "border-cyan bg-cyan/[.1] text-cyan" : "border-line bg-panel text-muted"
                        }`}
                      >
                        {s.label}
                      </button>
                      {on && (
                        <input
                          type="number" min={0} max={1} step={0.1}
                          value={pickedSegs[s.id]}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            const clamped = Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
                            setPickedSegs((p) => ({ ...p, [s.id]: clamped }));
                          }}
                          className="w-[52px] rounded-md border border-line bg-panel px-[6px] py-[3px] font-mono text-[11px] text-text tabnums focus:border-cyan focus:outline-none"
                        />
                      )}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* pick endpoint */}
          {endpoints.length > 0 && (
            <div className="mt-[10px]">
              <div className="mb-[5px] font-mono text-[10px] text-muted">变现出口</div>
              <select
                className={`${inputCls} appearance-none`}
                value={pickedEp}
                onChange={(e) => { setPickedEp(e.target.value === "" ? "" : Number(e.target.value)); setEpTouched(true); }}
              >
                <option value="">未定向</option>
                {endpoints.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            <button className={`${btnCls} border-lime/50 bg-lime/[.1] text-lime hover:bg-lime/[.18]`}
              onClick={applyComposition} disabled={busy === "assign"}>保存配置</button>
            <button className={`${btnCls} border-pink/50 bg-pink/[.08] text-pink hover:bg-pink/[.16]`}
              onClick={runClassify} disabled={busy === "llm"}>{busy === "llm" ? "归类中…" : "✨ LLM 归类人群"}</button>
          </div>

          {(segments.length === 0 && endpoints.length === 0) && (
            <p className="mt-[8px] font-mono text-[10px] leading-relaxed text-dim">
              先在上方建人群/出口，才能给账号分配占比与去向。
            </p>
          )}
        </section>

        <hr className="border-line" />

        {/* context + reset */}
        <section className="flex items-center justify-between gap-2">
          <div className="min-w-0 font-mono text-[10px] leading-relaxed text-dim">
            {flowSegLabels.length > 0 && <div className="truncate">在图人群：{flowSegLabels.join("、")}</div>}
            {flowEpLabels.length > 0 && <div className="truncate">在图出口：{flowEpLabels.join("、")}</div>}
          </div>
          <button className={`${btnCls} border-violet/50 bg-violet/[.1] text-violet hover:bg-violet/[.18]`}
            onClick={resetDemo} disabled={busy === "reset"}>{busy === "reset" ? "载入中…" : "↻ 重置为示例"}</button>
        </section>

        {msg && (
          <p className="rounded-lg border border-line bg-panel px-3 py-2 font-mono text-[11px] text-muted">{msg}</p>
        )}
      </div>
    </ChartCard>
  );
}
