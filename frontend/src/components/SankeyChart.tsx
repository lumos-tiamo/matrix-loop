import ReactECharts from "echarts-for-react";
import type { FlowData } from "../api/types";

/** Node accent by prefix: account→lime, segment→cyan, endpoint→violet. */
const KIND_TONE = {
  acct: "#B6FF3C",
  seg: "#4CD4F0",
  ep: "#A78BFA",
} as const;

const UNROUTED_TONE = "#5C6579"; // 未定向 endpoint reads as dim

type Kind = keyof typeof KIND_TONE;

function splitPrefix(name: string): { kind: Kind | null; label: string } {
  const idx = name.indexOf(":");
  if (idx === -1) return { kind: null, label: name };
  const prefix = name.slice(0, idx);
  const label = name.slice(idx + 1);
  if (prefix === "acct" || prefix === "seg" || prefix === "ep") {
    return { kind: prefix, label };
  }
  return { kind: null, label: name };
}

function toRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Polished BI Sankey: dark theme, prefix-colored nodes, translucent gradient links. */
export function SankeyChart({ flow, height = 520 }: { flow: FlowData; height?: number }) {
  const toneOf = (raw: string): string => {
    const { kind, label } = splitPrefix(raw);
    if (kind === "ep" && label === "未定向") return UNROUTED_TONE;
    return kind ? KIND_TONE[kind] : "#8A93A8";
  };

  const data = flow.nodes.map((n) => {
    const { kind, label } = splitPrefix(n.name);
    const tone = toneOf(n.name);
    const dim = kind === "ep" && label === "未定向";
    return {
      name: label, // display label (prefix stripped)
      itemStyle: {
        color: tone,
        borderColor: toRgba(tone, dim ? 0.35 : 0.9),
        borderWidth: 1,
        shadowBlur: dim ? 0 : 14,
        shadowColor: toRgba(tone, 0.35),
      },
      label: {
        color: dim ? "#8A93A8" : "#EAEDF3",
      },
    };
  });

  const links = flow.links.map((l) => {
    const from = toneOf(l.source);
    const to = toneOf(l.target);
    return {
      source: splitPrefix(l.source).label,
      target: splitPrefix(l.target).label,
      value: l.value,
      lineStyle: {
        color: {
          type: "linear" as const,
          x: 0,
          y: 0,
          x2: 1,
          y2: 0,
          colorStops: [
            { offset: 0, color: toRgba(from, 0.32) },
            { offset: 1, color: toRgba(to, 0.32) },
          ],
        },
      },
    };
  });

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "#151A26",
      borderColor: "#232B3C",
      borderWidth: 1,
      textStyle: { color: "#EAEDF3", fontFamily: "IBM Plex Mono" },
      formatter: (p: { dataType?: string; name?: string; value?: number; data?: { source?: string; target?: string } }) => {
        if (p.dataType === "edge" && p.data) {
          return `${p.data.source} → ${p.data.target}<br/><b>${Number(p.value ?? 0).toLocaleString()}</b> 流量`;
        }
        return `<b>${p.name}</b>`;
      },
    },
    series: [
      {
        type: "sankey" as const,
        left: 12,
        right: 120,
        top: 18,
        bottom: 18,
        nodeWidth: 14,
        nodeGap: 14,
        emphasis: { focus: "adjacency" as const },
        draggable: false,
        data,
        links,
        label: {
          color: "#EAEDF3",
          fontFamily: "IBM Plex Mono",
          fontSize: 12,
        },
        lineStyle: {
          curveness: 0.5,
        },
        levels: [
          { depth: 0, itemStyle: { color: KIND_TONE.acct } },
          { depth: 1, itemStyle: { color: KIND_TONE.seg } },
          { depth: 2, itemStyle: { color: KIND_TONE.ep } },
        ],
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} notMerge />;
}
