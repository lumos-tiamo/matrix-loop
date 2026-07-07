import { ChartCard } from "./ChartCard";

const DIMS: { key: string; label: string; color: string }[] = [
  { key: "growth", label: "涨粉", color: "#B6FF3C" },
  { key: "engagement", label: "互动", color: "#4CD4F0" },
  { key: "commercial", label: "商业", color: "#A78BFA" },
  { key: "positioning", label: "定位", color: "#FF6FB5" },
];

/**
 * 目标进度: four objective bars driven by the latest evaluation breakdown
 * (subscore / 100), annotated with each objective's configured weight.
 * Shows acceptance_criteria if the payload carries it.
 */
export function GoalProgress({
  weights,
  breakdown,
  acceptanceCriteria,
  style,
}: {
  weights: Record<string, number> | null;
  breakdown: Record<string, number> | null;
  acceptanceCriteria?: string | null;
  style?: React.CSSProperties;
}) {
  const w = weights ?? {};
  // weights are fractional (sum≈1); render as %.
  const wsum = Object.values(w).reduce((s, v) => s + (v || 0), 0);

  return (
    <ChartCard title={<>🎯 目标进度</>} pill="子分 / 100 · 权重" style={style} className="rise">
      {acceptanceCriteria && (
        <p className="mb-3 rounded-lg border border-line bg-panel px-3 py-2 font-mono text-[11px] text-muted">
          验收标准：{acceptanceCriteria}
        </p>
      )}
      <div className="flex flex-col gap-[13px]">
        {DIMS.map((d) => {
          const score = Math.max(0, Math.min(100, Math.round(breakdown?.[d.key] ?? 0)));
          const rawW = w[d.key] ?? 0;
          const weightPct = wsum > 0 ? Math.round((rawW / wsum) * 100) : Math.round(rawW * 100);
          return (
            <div key={d.key}>
              <div className="mb-[5px] flex items-center justify-between font-mono text-[11px] tabnums">
                <span className="text-text">
                  {d.label}
                  <span className="ml-2 text-muted">权重 {weightPct}%</span>
                </span>
                <span style={{ color: d.color }}>{score}</span>
              </div>
              <div className="h-[7px] overflow-hidden rounded-full bg-line">
                <i
                  className="block h-full rounded-full"
                  style={{ width: `${score}%`, background: d.color, boxShadow: `0 0 10px ${d.color}66` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </ChartCard>
  );
}
