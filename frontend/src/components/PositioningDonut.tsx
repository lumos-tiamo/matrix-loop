import ReactECharts from "echarts-for-react";
import { ChartCard } from "./ChartCard";
import type { PositioningDistribution } from "../api/types";

export function PositioningDonut({
  dist,
  style,
}: {
  dist: PositioningDistribution;
  style?: React.CSSProperties;
}) {
  const total = dist.clear + dist.ok + dist.scattered;
  const clearPct = total ? Math.round((dist.clear / total) * 100) : 0;
  const okPct = total ? Math.round((dist.ok / total) * 100) : 0;
  const scatteredPct = total ? Math.max(0, 100 - clearPct - okPct) : 0;

  const option = {
    backgroundColor: "transparent",
    series: [
      {
        type: "pie",
        radius: ["62%", "88%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: false,
        label: { show: true, position: "center", formatter: `清晰\n{b|${clearPct}%}`, rich: { b: { color: "#B6FF3C", fontSize: 18, fontFamily: "IBM Plex Mono", padding: [4, 0, 0, 0] } }, color: "#EAEDF3", fontSize: 11, fontFamily: "IBM Plex Mono" },
        labelLine: { show: false },
        data: [
          { value: dist.clear, name: "清晰垂直", itemStyle: { color: "#B6FF3C" } },
          { value: dist.ok, name: "尚可", itemStyle: { color: "#4CD4F0" } },
          { value: dist.scattered, name: "偏散待收敛", itemStyle: { color: "#A78BFA" } },
        ],
      },
    ],
  };

  return (
    <ChartCard title={<>🎯 矩阵定位分布</>} style={style} className="rise">
      <div className="flex items-center gap-[18px]">
        <div className="shrink-0" style={{ width: 120, height: 120 }}>
          <ReactECharts option={option} style={{ height: 120, width: 120 }} opts={{ renderer: "svg" }} />
        </div>
        <div className="flex flex-col gap-2 font-mono text-xs tabnums">
          <span><span className="text-lime">●</span> 清晰垂直 {clearPct}%</span>
          <span><span className="text-cyan">●</span> 尚可 {okPct}%</span>
          <span><span className="text-violet">●</span> 偏散待收敛 {scatteredPct}%</span>
        </div>
      </div>
    </ChartCard>
  );
}
