import type { FlywheelStep } from "../api/types";

const NC: Record<string, string> = {
  crawl: "var(--pink,#FF6FB5)", brief: "var(--violet,#A78BFA)", script: "var(--cyan,#4CD4F0)",
  video: "var(--cyan,#4CD4F0)", publish: "var(--lime,#B6FF3C)", track: "var(--cyan,#4CD4F0)",
  retro: "var(--violet,#A78BFA)", evaluate: "var(--violet,#A78BFA)", improve: "var(--lime,#B6FF3C)",
};

// custom line icons (24x24) keyed by step
const ICON: Record<string, JSX.Element> = {
  crawl: <><path d="M12 22a7 7 0 0 0 7-7c0-3-2-5.2-3.6-7.6C14 5.2 13 3.6 12 2c-.6 3-2 4.6-3.4 6.1C7 10.2 5 12 5 15a7 7 0 0 0 7 7z"/><path d="M12 22a3.3 3.3 0 0 0 3.3-3.3c0-1.8-1.7-3.1-3.3-5-1.6 1.9-3.3 3.2-3.3 5A3.3 3.3 0 0 0 12 22z"/></>,
  brief: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.6"/><circle cx="12" cy="12" r="1.1"/></>,
  script: <><path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4"/><path d="M10 8.5h3M10 12h6M10 15.5h6"/></>,
  video: <><rect x="3" y="6" width="12.5" height="12" rx="2.5"/><path d="M15.5 10.2l5.5-2.7v9l-5.5-2.7z"/></>,
  publish: <><path d="M21.5 3L2.6 10.2l7.3 2.9 2.9 7.3z"/><path d="M21.5 3L9.9 13.1"/></>,
  track: <path d="M3 12h3.4l2.4-6 4 13 2.5-7H21"/>,
  retro: <><path d="M20 12a8 8 0 0 1-13.7 5.6"/><path d="M4 12A8 8 0 0 1 17.7 6.4"/><path d="M17.7 2.6v3.8h-3.8"/><path d="M6.3 21.4v-3.8h3.8"/></>,
  evaluate: <><path d="M4 20h16"/><rect x="5.4" y="12" width="3.2" height="6" rx="1"/><rect x="10.4" y="7" width="3.2" height="11" rx="1"/><rect x="15.4" y="10" width="3.2" height="8" rx="1"/></>,
  improve: <><path d="M9.6 18.5h4.8M10.1 21.5h3.8"/><path d="M12 2.5A6.2 6.2 0 0 0 8.2 13.6c.9.7 1.3 1.4 1.3 2.4h5c0-1 .4-1.7 1.3-2.4A6.2 6.2 0 0 0 12 2.5z"/></>,
};

export function FlywheelChart({ steps, deliveredToday, autopilotCount, paused }:
  { steps: FlywheelStep[]; deliveredToday: number; autopilotCount: number; paused: boolean }) {
  const R = 250;
  return (
    <div className="relative mx-auto" style={{ width: 600, height: 600 }}>
      <svg viewBox="0 0 600 600" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id="fwflow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#B6FF3C"/><stop offset=".5" stopColor="#4CD4F0"/><stop offset="1" stopColor="#A78BFA"/>
          </linearGradient>
          <radialGradient id="fwsweep"><stop offset="0" stopColor="rgba(182,255,60,0)"/><stop offset="1" stopColor="rgba(182,255,60,.5)"/></radialGradient>
        </defs>
        <circle cx="300" cy="300" r={R} fill="none" stroke="var(--line,#232B3C)" strokeWidth="1.5"/>
        {!paused && (
          <circle cx="300" cy="300" r={R} fill="none" stroke="url(#fwflow)" strokeWidth="2.5"
            strokeLinecap="round" strokeDasharray="6 16" className="fw-flow"/>
        )}
        {!paused && (
          <g className="fw-sweep"><path d="M300 300 L300 50 A250 250 0 0 1 476 124 Z" fill="url(#fwsweep)" opacity=".18"/></g>
        )}
      </svg>

      {/* core */}
      <div className="absolute left-1/2 top-1/2 flex flex-col items-center justify-center gap-[2px] text-center"
        style={{ transform: "translate(-50%,-50%)", width: 230, height: 230, borderRadius: "50%",
          border: "1px solid var(--line,#232B3C)",
          background: "radial-gradient(circle at 50% 40%, rgba(182,255,60,.10), rgba(17,21,31,.9) 68%)" }}>
        <div className="font-display text-[44px] font-black leading-none tracking-tight text-lime tabnums">
          {deliveredToday}<span className="text-[14px] font-semibold text-muted"> 条/日</span></div>
        <div className="font-mono text-[11px] text-muted">今日已交付</div>
        <div className="mt-[6px] font-mono text-[12px] text-text">在跑 <b className="text-cyan">{autopilotCount}</b> 个自动驾驶账号</div>
        <div className={`mt-2 font-mono text-[10px] uppercase tracking-[.22em] ${paused ? "text-warn" : "text-good"}`}>
          {paused ? "● PAUSED" : "● SELF-SPINNING"}</div>
      </div>

      {/* nodes */}
      {steps.slice(0, 9).map((s, i) => {
        const angle = -90 + i * 40;
        const on = s.status === "ok";
        return (
          <div key={s.key} className="absolute left-1/2 top-1/2 text-center"
            style={{ width: 118, marginLeft: -59, marginTop: -34,
              transform: `rotate(${angle}deg) translateY(-${R}px) rotate(${-angle}deg)`, ["--nc" as string]: NC[s.key] } as React.CSSProperties}>
            <div className={`relative mx-auto flex items-center justify-center rounded-[17px] border transition-colors ${on ? "fw-node-on" : ""}`}
              style={{ width: 58, height: 58, color: NC[s.key],
                background: on ? "color-mix(in oklab, var(--nc) 13%, transparent)" : "var(--panel2,#151A26)",
                borderColor: on ? NC[s.key] : "var(--line,#232B3C)",
                boxShadow: on ? "0 0 22px color-mix(in oklab, var(--nc) 28%, transparent)" : "none" }}>
              <svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor"
                strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{ICON[s.key]}</svg>
              <span className="absolute -left-[7px] -top-[7px] flex h-[19px] w-[19px] items-center justify-center rounded-full border border-line bg-bg font-mono text-[10px] text-muted">{i + 1}</span>
            </div>
            <div className="mt-[7px] font-sans text-[12px] font-bold text-text">{s.label}</div>
            <div className="mt-[1px] font-mono text-[10.5px]" style={{ color: on ? NC[s.key] : "var(--muted,#8A97AC)" }}>{s.count}</div>
          </div>
        );
      })}
    </div>
  );
}
