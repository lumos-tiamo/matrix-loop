import ReactECharts from "echarts-for-react";
import type { SnapshotOut } from "../api/types";

export function TrendChart({ snapshots }: { snapshots: SnapshotOut[] }) {
  const ordered = [...snapshots].sort((a, b) => a.ts.localeCompare(b.ts));
  const option = {
    backgroundColor: "transparent",
    grid: { top: 24, right: 16, bottom: 24, left: 48 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: ordered.map((s) => s.ts.slice(5, 10)), axisLine: { lineStyle: { color: "#232A38" } }, axisLabel: { color: "#8B93A7", fontFamily: "IBM Plex Mono" } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#232A38" } }, axisLabel: { color: "#8B93A7", fontFamily: "IBM Plex Mono" } },
    series: [{ type: "line", smooth: true, data: ordered.map((s) => s.followers ?? 0), lineStyle: { color: "#B6FF3C", width: 2 }, itemStyle: { color: "#B6FF3C" }, areaStyle: { color: "rgba(182,255,60,0.08)" } }],
  };
  return <ReactECharts option={option} style={{ height: 200 }} />;
}
