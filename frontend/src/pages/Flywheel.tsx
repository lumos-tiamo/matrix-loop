import { useState } from "react";
import { api } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { AccountCard } from "../components/AccountCard";
import { EventFeed } from "../components/EventFeed";
import { GlassButton } from "../components/GlassButton";

export function Flywheel() {
  const accounts = usePolling(() => api.getFlywheelAccounts(), 4000);
  const state = usePolling(() => api.getFlywheel(), 4000);
  const events = usePolling(() => api.getFlywheelEvents(), 4000);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const s = state.data;
  const paused = s?.paused ?? false;

  async function togglePause() {
    setBusy(true);
    setErr(null);
    try {
      paused ? await api.resumeFlywheel() : await api.pauseFlywheel();
      state.reload();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const list = accounts.data ?? [];

  return (
    <div className="mx-auto max-w-[1120px]">
      <header className="glass mb-[18px] flex flex-wrap items-center gap-x-3.5 gap-y-2 rounded-[22px] px-5 py-3.5">
        <span className="flex h-[34px] w-[34px] items-center justify-center rounded-[11px] bg-gradient-to-br from-blue1 to-blue2 text-[16px] font-extrabold text-white shadow-[0_8px_20px_-4px_rgba(47,123,255,0.6)]">
          ◎
        </span>
        <span className="text-[17px] font-bold tracking-[-0.01em]">自动驾驶飞轮</span>
        <span className="inline-flex items-center gap-[7px] rounded-full border border-cyan/30 bg-cyan/[.12] px-[11px] py-1 text-[11px] font-semibold text-cyan">
          <span className="live-dot" />
          实时 · 4s
        </span>

        <div className="ml-auto flex items-center gap-[22px]">
          <span className="text-[12px] text-muted2">
            今日成本 <b className="text-[15px] font-bold text-txt">${s?.today_cost ?? 0}</b>
          </span>
          <span className="text-[12px] text-muted2">
            自驾账号 <b className="text-[15px] font-bold text-txt">{s?.autopilot_accounts ?? 0}</b>
          </span>
          <span className="text-[12px] text-muted2">
            待审 <b className="text-[15px] font-bold text-amber">{s?.pending_review ?? 0}</b>
          </span>
          <span className="text-[12px] text-muted2">
            在飞 <b className="text-[15px] font-bold text-txt">{s?.status_counts?.running ?? 0}</b>
          </span>
          <GlassButton
            variant="secondary"
            onClick={togglePause}
            disabled={busy}
            aria-label="暂停或恢复飞轮"
            className="disabled:opacity-50"
          >
            {paused ? "▶ 恢复" : "⏸ 暂停"}
          </GlassButton>
        </div>
      </header>

      {(err || state.error) && (
        <div className="mb-3 font-mono text-[12px] text-err">操作失败：{err ?? state.error}</div>
      )}

      <div className="grid grid-cols-[1fr_300px] gap-4">
        <div className="flex flex-col gap-3.5">
          {list.map((a) => (
            <AccountCard key={a.account_id} a={a} />
          ))}
          {list.length === 0 && (
            <div className="glass px-4 py-10 text-center text-[12.5px] text-muted2">
              暂无自动驾驶账号
            </div>
          )}
        </div>

        <EventFeed events={events.data ?? []} />
      </div>
    </div>
  );
}
