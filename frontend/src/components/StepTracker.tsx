export const STEPS = ["sync","evaluate","topic","script","video","approve","publish","track"];
export type SegState = "done" | "active" | "upcoming" | "warn";

export function segState(i: number, stepIndex: number, status: string): SegState {
  if ((status === "blocked" || status === "error") && i === stepIndex) return "warn";
  if (i < stepIndex) return "done";
  if (i === stepIndex) return "active";
  return "upcoming";
}
const SEG: Record<SegState, string> = {
  done: "bg-gradient-to-r from-ok to-[#2fbf78]",
  active: "bg-gradient-to-r from-run to-blue2 shadow-[0_0_10px_rgba(76,212,240,0.5)]",
  upcoming: "bg-white/10",
  warn: "bg-block",
};
export function StepTracker({ stepIndex, status }: { stepIndex: number; status: string }) {
  return (
    <div>
      <div className="flex items-center">
        {STEPS.map((s, i) => {
          const st = segState(i, stepIndex, status);
          const bead = st === "upcoming" ? "bg-white/15"
            : st === "warn" ? "bg-block"
            : st === "active" ? "bg-run shadow-[0_0_0_4px_rgba(76,212,240,0.18)]" : "bg-ok";
          return (
            <div key={s} data-step={s} className="flex items-center flex-1 last:flex-none">
              <span className={`w-2 h-2 rounded-full -mx-px z-10 ${bead}`} />
              {i < STEPS.length - 1 && <span className={`h-[3px] flex-1 rounded ${SEG[st]}`} />}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[9px] text-dim2 mt-1.5 px-0.5">
        {STEPS.map((s, i) => <span key={s} className={i === stepIndex ? "text-run font-semibold" : ""}>{s}</span>)}
      </div>
    </div>
  );
}
