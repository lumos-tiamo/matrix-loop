import { Link } from "react-router-dom";
import { ChartCard } from "./ChartCard";
import type { OverviewAlert } from "../api/types";

const KIND_META: Record<string, { color: string; action: string; go: boolean }> = {
  no_progress: { color: "#FFB020", action: "介入", go: true },
  pending_drafts: { color: "#4CD4F0", action: "审核", go: false },
  followers_drop: { color: "#FF5C7A", action: "查看", go: false },
  positioning_suggestion: { color: "#B6FF3C", action: "决定", go: true },
};

export function AlertCenter({ alerts, style }: { alerts: OverviewAlert[]; style?: React.CSSProperties }) {
  return (
    <ChartCard
      title={<>⚠️ 告警中心</>}
      pill={`${alerts.length} 需处理`}
      style={style}
      className="rise"
    >
      {alerts.length === 0 ? (
        <p className="font-mono text-xs text-muted">暂无告警，一切正常。</p>
      ) : (
        <div>
          {alerts.slice(0, 8).map((a, i) => {
            const meta = KIND_META[a.kind] ?? { color: "#8A93A8", action: "查看", go: false };
            return (
              <div
                key={`${a.account_id}-${a.kind}-${i}`}
                className="mb-2 flex items-center gap-[10px] rounded-[11px] border border-line bg-panel px-3 py-[10px]"
              >
                <span
                  className="h-[9px] w-[9px] shrink-0 rounded-full"
                  style={{ background: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
                />
                <span className="min-w-0 flex-1 truncate text-sm">
                  <span className="font-mono">{a.handle}</span>{" "}
                  <span className="text-muted">{a.detail}</span>
                </span>
                <Link
                  to={`/accounts/${a.account_id}`}
                  className={`ml-auto shrink-0 rounded-[7px] border px-[9px] py-1 font-mono text-[11px] ${
                    meta.go ? "border-lime text-lime" : "border-line text-text"
                  }`}
                >
                  {meta.action}
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </ChartCard>
  );
}
