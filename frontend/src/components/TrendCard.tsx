import ReactECharts from "echarts-for-react";
import { ChartCard } from "./ChartCard";
import type { TrendPoint } from "../api/types";

/** Matrix-wide followers (lime) + engagement (cyan) area chart with dual y-axes. */
export function TrendCard({ trend, style }: { trend: TrendPoint[]; style?: React.CSSProperties }) {
  const dates = trend.map((t) => t.date.slice(5));
  const followers = trend.map((t) => t.followers);
  const engagement = trend.map((t) => Number((t.engagement * 100).toFixed(2)));

  const axisLabel = { color: "#8A93A8", fontFamily: "IBM Plex Mono", fontSize: 10 };
  const option = {
    backgroundColor: "transparent",
    grid: { top: 16, right: 44, bottom: 24, left: 48 },
    tooltip: { trigger: "axis", backgroundColor: "#151A26", borderColor: "#232B3C", textStyle: { color: "#EAEDF3" } },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: "#232B3C" } },
      axisLabel,
    },
    yAxis: [
      { type: "value", splitLine: { lineStyle: { color: "#232B3C" } }, axisLabel },
      { type: "value", position: "right", splitLine: { show: false }, axisLabel: { ...axisLabel, formatter: "{value}%" } },
    ],
    series: [
      {
        name: "粉丝",
        type: "line",
        smooth: true,
        symbol: "none",
        data: followers,
        lineStyle: { color: "#B6FF3C", width: 2.5 },
        itemStyle: { color: "#B6FF3C" },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(182,255,60,0.35)" },
              { offset: 1, color: "rgba(182,255,60,0)" },
            ],
          },
        },
      },
      {
        name: "互动量",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        symbol: "none",
        data: engagement,
        lineStyle: { color: "#4CD4F0", width: 2 },
        itemStyle: { color: "#4CD4F0" },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(76,212,240,0.28)" },
              { offset: 1, color: "rgba(76,212,240,0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <ChartCard title={<>📈 大盘涨粉趋势</>} pill="全矩阵 · 趋势" style={style} className="rise">
      {trend.length === 0 ? (
        <p className="font-mono text-xs text-muted">暂无趋势数据。</p>
      ) : (
        <ReactECharts option={option} style={{ height: 188 }} opts={{ renderer: "svg" }} />
      )}
      <div className="mt-[6px] flex gap-4 font-mono text-[11px] text-muted tabnums">
        <span className="text-lime">● 粉丝</span>
        <span className="text-cyan">● 互动量</span>
      </div>
    </ChartCard>
  );
}
