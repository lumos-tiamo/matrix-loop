import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import type { FlywheelState } from "../api/types";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";
import { FlywheelChart } from "../components/FlywheelChart";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok", twitter: "X",
  weixin_video: "视频号", weixin_gzh: "公众号", youtube: "YouTube", instagram: "IG", bilibili: "B站",
};
const EMPTY: FlywheelState = { paused: false, autopilot_accounts: 0, pending_review: 0, steps: [], accounts: [], events: [] };

export function Flywheel() {
  const fw = useAsync(() => api.getFlywheel(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const d: FlywheelState = fw.data ?? EMPTY;

  const delivered = useMemo(
    () => (d.steps.find((s) => s.key === "publish")?.count ?? 0), [d.steps]);

  async function toggleAutopilot(id: number, enabled: boolean) {
    setBusy(`ap-${id}`);
    try { setErr(null); await api.setAutopilot(id, enabled); fw.reload(); } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  }
  async function togglePause() {
    setBusy("pause");
    try { setErr(null); d.paused ? await api.resumeFlywheel() : await api.pauseFlywheel(); fw.reload(); } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">内容自转<span className="text-lime">飞轮</span></h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">爬爆款 → 定调 → 脚本 → 视频 → 发布 → 追踪 → 复盘 → 评估 → 改进 · <span className="text-warn">下班无人值守</span></p>
        </div>
        <div className="flex-1" />
        <button onClick={togglePause} disabled={busy !== null} aria-label="暂停或恢复飞轮"
          className={`rounded-lg border px-4 py-2 font-mono text-xs transition-colors disabled:opacity-50 ${d.paused ? "border-good/50 bg-good/[.1] text-good" : "border-alert/50 bg-alert/[.08] text-alert"}`}>
          {d.paused ? "▶ 恢复飞轮" : "⏸ 暂停飞轮"}
        </button>
      </div>

      {(fw.error || err) && <div className="px-1 pb-3 font-mono text-alert">操作失败：{err || fw.error}</div>}

      <div className="mb-[14px] grid grid-cols-2 gap-[14px] md:grid-cols-4">
        <StatTile label="今日交付(发布)" value={String(delivered)} accent />
        <StatTile label="自动驾驶账号" value={`${d.autopilot_accounts} / ${d.accounts.length}`} />
        <StatTile label="待人工审核" value={String(d.pending_review)} />
        <StatTile label="飞轮状态" value={d.paused ? "已暂停" : "自转中"} />
      </div>

      <div className="grid gap-[14px] lg:grid-cols-[1.55fr_.95fr]">
        <ChartCard title="🌀 内容自转飞轮" pill="9 步 · 实时" glow className="rise min-h-[660px]">
          <FlywheelChart steps={d.steps} deliveredToday={delivered} autopilotCount={d.autopilot_accounts} paused={d.paused} loading={fw.loading} />
        </ChartCard>

        <div className="flex flex-col gap-[14px]">
          <ChartCard title="🛩 自动驾驶账号" pill={`${d.autopilot_accounts} 开`}>
            <div className="space-y-[2px]">
              {d.accounts.map((a) => (
                <div key={a.id} className="flex items-center gap-3 border-t border-line py-[10px] first:border-t-0">
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-[13px] font-bold text-text">{a.handle}</div>
                    <div className="font-mono text-[10.5px] text-muted">{PLATFORM_LABEL[a.platform] ?? a.platform}</div>
                  </div>
                  <button onClick={() => toggleAutopilot(a.id, !a.autopilot)} disabled={busy !== null}
                    aria-label={`切换 ${a.handle} 自动驾驶`}
                    className={`relative h-6 w-11 rounded-full border transition-colors disabled:opacity-50 ${a.autopilot ? "border-lime bg-lime/[.18]" : "border-line bg-panel2"}`}>
                    <span className={`absolute top-[2px] h-[18px] w-[18px] rounded-full transition-all ${a.autopilot ? "left-[22px] bg-lime" : "left-[2px] bg-muted"}`} />
                  </button>
                </div>
              ))}
              {d.accounts.length === 0 && <p className="py-6 text-center font-mono text-[11px] text-muted">还没有账号。</p>}
            </div>
          </ChartCard>

          <ChartCard title="⚡ 飞轮流水" pill="实时">
            <div className="space-y-[2px]">
              {d.events.map((e, i) => (
                <div key={`${e.ts ?? "?"}-${e.step}-${e.account_id ?? "?"}-${i}`} className="flex items-baseline gap-[10px] border-t border-line py-[9px] font-mono text-[11.5px] first:border-t-0">
                  <span className="text-dim">{e.ts ? e.ts.slice(11, 16) : "--:--"}</span>
                  <span className={e.status === "ok" ? "text-cyan" : e.status === "blocked" ? "text-warn" : e.status === "error" ? "text-alert" : "text-muted"}>{e.step}</span>
                  <span className="min-w-0 flex-1 truncate text-muted">{e.detail}</span>
                </div>
              ))}
              {d.events.length === 0 && <p className="py-6 text-center font-mono text-[11px] text-muted">飞轮还没转过 —— 打开账号自动驾驶或跑一批后这里出流水。</p>}
            </div>
          </ChartCard>
        </div>
      </div>
    </div>
  );
}
