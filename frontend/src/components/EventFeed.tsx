import type { FlywheelEventLive } from "../api/types";

const ICON: Record<string, { c: string; g: string }> = {
  ok: { c: "text-ok bg-ok/16", g: "✓" }, blocked: { c: "text-block bg-block/16", g: "⚠" },
  error: { c: "text-err bg-err/16", g: "✕" }, running: { c: "text-run bg-run/16", g: "▶" },
};

export function EventFeed({ events }: { events: FlywheelEventLive[] }) {
  return (
    <aside className="glass p-4 self-start">
      <h4 className="text-[13px] font-semibold flex items-center gap-2 mb-3.5">实时事件流 <span className="live-dot" /></h4>
      {events.map((e) => {
        const ic = ICON[e.status] ?? ICON.running;
        return (
          <div key={e.id} className="flex gap-2.5 py-2 border-b border-white/5 last:border-0">
            <span className={`w-[18px] h-[18px] rounded-md flex items-center justify-center text-[10px] mt-0.5 ${ic.c}`}>{ic.g}</span>
            <div className="text-[11.5px]"><b>{e.account_handle ?? "—"}</b> · {e.step} {e.detail ?? e.status}
              <div className="text-dim2 text-[10px] font-mono mt-0.5">{new Date(e.ts).toLocaleTimeString()}</div></div>
          </div>
        );
      })}
    </aside>
  );
}
