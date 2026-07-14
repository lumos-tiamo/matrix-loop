import type { FlywheelAccountLive } from "../api/types";
import { StatusPill } from "./StatusPill";
import { StepTracker } from "./StepTracker";

const PLAT: Record<string, string> = { tiktok: "♪ TikTok", twitter: "𝕏 Twitter", youtube: "▶ YouTube", instagram: "✦ Instagram" };
const fmtDur = (s: number | null) => s == null ? "—" : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function AccountCard({ a }: { a: FlywheelAccountLive }) {
  const plat = PLAT[a.platform] ?? a.platform;
  if (a.status === "ok" || a.status === "idle") {
    return (
      <div className="glass flex items-center gap-3 px-4 py-3">
        <span className="font-semibold text-[14px]">{a.handle}</span>
        <span className="text-[10.5px] text-muted2 border border-white/10 rounded-lg px-2 py-0.5">{plat}</span>
        <StatusPill status={a.status} />
        <span className="ml-auto flex gap-4 items-center text-[11.5px] text-muted2">
          <span>综合分 <b className="text-lime">{a.kpis.score ?? "—"}</b></span>
          <span>本轮 <b className="text-lime">${a.cost_cycle}</b></span>
          <span className="font-mono">下一轮 {fmtDur(a.next_run_eta_sec)}</span>
        </span>
      </div>
    );
  }
  const borderCls = a.status === "running" ? "border-run/34" : a.status === "blocked" ? "border-block/34" : "border-err/34";
  return (
    <div className={`glass p-[18px] ${borderCls}`}>
      <div className="flex items-center gap-2.5 mb-3.5">
        <span className="font-semibold text-[14px]">{a.handle}</span>
        <span className="text-[10.5px] text-muted2 border border-white/10 rounded-lg px-2 py-0.5">{plat}</span>
        <StatusPill status={a.status} />
        <span className="ml-auto font-mono text-[11.5px] text-muted2 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1">
          ⏱ {a.status === "blocked" ? `卡 ${fmtDur(a.elapsed_sec)}` : fmtDur(a.elapsed_sec)}
        </span>
      </div>
      <StepTracker stepIndex={a.step_index} status={a.status} />
      <div className="flex items-end gap-5 mt-3.5 text-[11px]">
        <div><div className="text-muted2">粉丝</div><div className="font-bold text-[14px]">{(a.kpis.followers ?? 0).toLocaleString()} {a.kpis.followers_delta != null && <small className="text-ok">▲{a.kpis.followers_delta}%</small>}</div></div>
        <div><div className="text-muted2">近7日播放</div><div className="font-bold text-[14px]">{(a.kpis.views_7d ?? 0).toLocaleString()}</div></div>
        <div><div className="text-muted2">综合分</div><div className="font-bold text-[14px] text-lime">{a.kpis.score ?? "—"}</div></div>
        <div><div className="text-muted2">本轮成本</div><div className="font-bold text-[14px] text-lime">${a.cost_cycle}</div></div>
        <div className="ml-auto text-right"><div className="text-muted2">数据同步</div><div className="text-muted2 text-[12px]">{a.synced_at ? new Date(a.synced_at).toLocaleTimeString() : "—"}</div></div>
      </div>
      {a.status === "blocked" && (
        <div className="mt-3 text-[11.5px] text-block bg-block/8 border border-block/20 rounded-xl px-3 py-2 flex items-center gap-2">
          ⏸ {a.blocked_reason ?? "等待处理"} · 卡在 {a.current_step} 步
          <a href="/video" className="ml-auto underline cursor-pointer">→ 去成片审核</a>
        </div>
      )}
    </div>
  );
}
