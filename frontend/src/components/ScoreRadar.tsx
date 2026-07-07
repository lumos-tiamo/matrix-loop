import ReactECharts from "echarts-for-react";

const DIMS: { key: string; name: string }[] = [
  { key: "growth", name: "涨粉" }, { key: "engagement", name: "互动" },
  { key: "commercial", name: "商业" }, { key: "positioning", name: "定位" },
];

export function ScoreRadar({ breakdown }: { breakdown: Record<string, number> }) {
  const option = {
    backgroundColor: "transparent",
    radar: {
      indicator: DIMS.map((d) => ({ name: d.name, max: 100 })),
      axisName: { color: "#8B93A7", fontFamily: "IBM Plex Mono" },
      splitLine: { lineStyle: { color: "#232A38" } }, splitArea: { show: false }, axisLine: { lineStyle: { color: "#232A38" } },
    },
    series: [{ type: "radar", data: [{ value: DIMS.map((d) => breakdown[d.key] ?? 0), lineStyle: { color: "#B6FF3C" }, areaStyle: { color: "rgba(182,255,60,0.15)" }, itemStyle: { color: "#B6FF3C" } }] }],
  };
  return <ReactECharts option={option} style={{ height: 200 }} />;
}
