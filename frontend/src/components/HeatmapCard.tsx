import { ChartCard } from "./ChartCard";
import type { PlatformHealth } from "../api/types";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  twitter: "X",
  x: "X",
  weixin_video: "视频号",
  wechat_video: "视频号",
};

const DIMS: { key: keyof Omit<PlatformHealth, "platform">; label: string }[] = [
  { key: "growth", label: "涨粉" },
  { key: "engagement", label: "互动" },
  { key: "commercial", label: "商业" },
  { key: "positioning", label: "定位" },
];

/** score -> cell background (red -> amber -> lime), matching mockup thresholds. */
function cellStyle(score: number): { background: string; color: string } {
  if (score >= 85) return { background: "#B6FF3C", color: "#0A0D12" };
  if (score >= 65) return { background: "#8FE24A", color: "#0A0D12" };
  if (score >= 45) return { background: "#FFB020", color: "#0A0D12" };
  return { background: "#FF5C7A", color: "#fff" };
}

export function HeatmapCard({ data, style }: { data: PlatformHealth[]; style?: React.CSSProperties }) {
  return (
    <ChartCard title={<>🌐 平台健康热力图</>} pill="按平台 × 目标 达标率" style={style} className="rise">
      {data.length === 0 ? (
        <p className="font-mono text-xs text-muted">暂无评估数据。</p>
      ) : (
        <div
          className="grid gap-[6px] font-mono text-[11px]"
          style={{ gridTemplateColumns: "90px repeat(4,1fr)" }}
        >
          <div />
          {DIMS.map((d) => (
            <div key={d.key} className="flex items-center justify-center py-1 text-muted">
              {d.label}
            </div>
          ))}
          {data.map((row) => (
            <RowCells key={row.platform} row={row} />
          ))}
        </div>
      )}
    </ChartCard>
  );
}

function RowCells({ row }: { row: PlatformHealth }) {
  return (
    <>
      <div className="flex items-center gap-[6px] text-text">
        {PLATFORM_LABEL[row.platform] ?? row.platform}
      </div>
      {DIMS.map((d) => {
        const v = Math.round(row[d.key] as number);
        const s = cellStyle(v);
        return (
          <div
            key={d.key}
            className="flex h-[34px] items-center justify-center rounded-lg font-semibold"
            style={{ background: s.background, color: s.color }}
          >
            {v}
          </div>
        );
      })}
    </>
  );
}
