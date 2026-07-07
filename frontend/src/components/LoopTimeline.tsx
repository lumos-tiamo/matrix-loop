import type { LoopRunOut } from "../api/types";
import { StatusDot } from "./StatusDot";

export function LoopTimeline({ runs }: { runs: LoopRunOut[] }) {
  const ordered = [...runs].sort((a, b) => b.ts.localeCompare(a.ts));
  return (
    <ul className="space-y-3">
      {ordered.map((r) => {
        const raw = r.verify_result?.delta;
        const delta = typeof raw === "number" ? raw : null;
        return (
          <li key={r.id} className="border-l-2 border-line pl-3">
            <div className="flex items-center gap-3 font-mono text-xs text-muted">
              <span>{r.ts.slice(0, 16).replace("T", " ")}</span>
              <StatusDot status={r.status} />
              {delta != null && <span className={delta > 0 ? "text-good" : "text-muted"}>Δ {delta > 0 ? "+" : ""}{delta}</span>}
            </div>
            {r.diagnosis && <p className="text-sm mt-1">{r.diagnosis}</p>}
          </li>
        );
      })}
    </ul>
  );
}
