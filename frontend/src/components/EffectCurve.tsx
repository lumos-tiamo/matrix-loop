import ReactECharts from "echarts-for-react";
import { ChartCard } from "./ChartCard";
import type { LoopRunOut } from "../api/types";

/**
 * Loop 见效曲线: composite_score across loop runs (chronological), conveying
 * whether the self-correcting loop moved the needle over time.
 */
export function EffectCurve({ runs, style }: { runs: LoopRunOut[]; style?: React.CSSProperties }) {
  const ordered = [...runs]
    .filter((r) => r.evaluation != null)
    .sort((a, b) => a.ts.localeCompare(b.ts));

  const labels = ordered.map((_, i) => `第${i + 1}轮`);
  const scores = ordered.map((r) => Number(r.evaluation!.composite_score.toFixed(1)));

  // per-point color: green if this round improved on the previous, muted otherwise
  const points = scores.map((s, i) => {
    const up = i > 0 ? s >= scores[i - 1] : true;
    return { value: s, itemStyle: { color: up ? "#38E08A" : "#FFB020" } };
  });

  const first = scores[0];
  const last = scores[scores.length - 1];
  const totalDelta = ordered.length >= 2 ? Number((last - first).toFixed(1)) : 0;
  const effective = totalDelta > 0;

  const axisLabel = { color: "#8A93A8", fontFamily: "IBM Plex Mono", fontSize: 10 };
  const option = {
    backgroundColor: "transparent",
    grid: { top: 18, right: 18, bottom: 24, left: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#151A26", borderColor: "#232B3C", textStyle: { color: "#EAEDF3" } },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#232B3C" } },
      axisLabel,
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: "#232B3C" } },
      axisLabel,
    },
    series: [
      {
        type: "line",
        smooth: true,
        symbolSize: 8,
        data: points,
        lineStyle: { color: "#B6FF3C", width: 2.5 },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(182,255,60,0.30)" },
              { offset: 1, color: "rgba(182,255,60,0)" },
            ],
          },
        },
        label: {
          show: true,
          position: "top",
          color: "#EAEDF3",
          fontFamily: "IBM Plex Mono",
          fontSize: 10,
          formatter: "{c}",
        },
      },
    ],
  };

  const pill =
    ordered.length < 2
      ? "首轮基线"
      : effective
        ? `见效 ↑ +${totalDelta}`
        : totalDelta === 0
          ? "持平 →"
          : `回落 ↓ ${totalDelta}`;

  return (
    <ChartCard title={<>📈 Loop 见效曲线</>} pill={pill} style={style} className="rise">
      {ordered.length === 0 ? (
        <p className="font-mono text-xs text-muted">还没有评估记录，先跑一轮 Loop。</p>
      ) : (
        <ReactECharts option={option} style={{ height: 200 }} opts={{ renderer: "svg" }} />
      )}
      <div className="mt-[6px] font-mono text-[11px] text-muted tabnums">
        <span className="text-good">●</span> 较上轮上升 &nbsp;
        <span className="text-warn">●</span> 较上轮下降
      </div>
    </ChartCard>
  );
}
