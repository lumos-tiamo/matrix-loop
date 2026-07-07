import { Link } from "react-router-dom";
import { ChartCard } from "./ChartCard";
import type { TopMover } from "../api/types";

const BAR_COLORS = ["#B6FF3C", "#4CD4F0", "#A78BFA", "#FF6FB5"];

function fmtDelta(n: number): string {
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const val = abs >= 1000 ? `${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}K` : String(abs);
  return `${sign}${val}`;
}

export function MoversCard({ movers, style }: { movers: TopMover[]; style?: React.CSSProperties }) {
  const top = movers.slice(0, 6);
  const maxAbs = Math.max(1, ...top.map((m) => Math.abs(m.delta_followers)));

  return (
    <ChartCard title={<>🚀 本周飙升 Top</>} style={style} className="rise">
      {top.length === 0 ? (
        <p className="font-mono text-xs text-muted">暂无涨跌数据。</p>
      ) : (
        <div className="flex flex-col gap-[11px] tabnums">
          {top.map((m, i) => {
            const pct = Math.max(6, Math.round((Math.abs(m.delta_followers) / maxAbs) * 100));
            const down = m.delta_followers < 0;
            const color = down ? "#FF5C7A" : BAR_COLORS[i % BAR_COLORS.length];
            return (
              <div key={m.account_id} className="flex items-center gap-3">
                <Link
                  to={`/accounts/${m.account_id}`}
                  className="w-24 shrink-0 truncate font-mono text-xs hover:text-lime"
                >
                  {m.handle}
                </Link>
                <div className="h-[5px] flex-1 overflow-hidden rounded bg-line">
                  <i
                    className="block h-full rounded"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
                <span className={`w-14 shrink-0 text-right font-mono text-xs ${down ? "text-alert" : "text-good"}`}>
                  {fmtDelta(m.delta_followers)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </ChartCard>
  );
}
