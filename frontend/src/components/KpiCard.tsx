import ReactECharts from "echarts-for-react";

export type KpiTone = "text" | "lime" | "cyan" | "violet" | "warn";

const TONE_HEX: Record<KpiTone, string> = {
  text: "#EAEDF3",
  lime: "#B6FF3C",
  cyan: "#4CD4F0",
  violet: "#A78BFA",
  warn: "#FFB020",
};

const TONE_TEXT: Record<KpiTone, string> = {
  text: "text-text",
  lime: "text-lime",
  cyan: "text-cyan",
  violet: "text-violet",
  warn: "text-warn",
};

/** Mini sparkline (no axes) rendered with ECharts. */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const option = {
    backgroundColor: "transparent",
    grid: { top: 2, right: 2, bottom: 2, left: 2 },
    xAxis: { type: "category", show: false, boundaryGap: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    series: [
      {
        type: "line",
        data,
        smooth: true,
        symbol: "none",
        lineStyle: { color, width: 2 },
        areaStyle: { color, opacity: 0.12 },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 26, width: 70 }} opts={{ renderer: "svg" }} />;
}

export function KpiCard({
  label,
  value,
  delta,
  deltaTone = "up",
  tone = "text",
  spark,
  glow = false,
  style,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  tone?: KpiTone;
  spark?: number[];
  glow?: boolean;
  style?: React.CSSProperties;
}) {
  const deltaClass =
    deltaTone === "up" ? "text-good" : deltaTone === "down" ? "text-alert" : "text-muted";
  return (
    <div
      className={`relative overflow-hidden glass p-4 rise ${
        glow ? "shadow-[inset_0_0_0_1px_rgba(182,255,60,0.18)]" : ""
      }`}
      style={style}
    >
      <div className="font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-[6px] font-display text-[34px] font-extrabold tracking-tight tabnums ${TONE_TEXT[tone]}`}>
        {value}
      </div>
      {delta && <div className={`mt-[2px] font-mono text-xs ${deltaClass}`}>{delta}</div>}
      {spark && spark.length > 1 && (
        <div className="absolute bottom-3 right-3 opacity-90">
          <Sparkline data={spark} color={TONE_HEX[tone]} />
        </div>
      )}
    </div>
  );
}
