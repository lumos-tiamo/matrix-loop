import type { ReactNode } from "react";

/** Gradient BI card surface (linear-gradient panel2->panel + line border + rounded-2xl). */
export function ChartCard({
  title,
  pill,
  children,
  className = "",
  glow = false,
  style,
}: {
  title?: ReactNode;
  pill?: ReactNode;
  children: ReactNode;
  className?: string;
  glow?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-line bg-gradient-to-b from-panel2 to-panel p-4 md:p-[18px] ${
        glow ? "shadow-[inset_0_0_0_1px_rgba(182,255,60,0.18)]" : ""
      } ${className}`}
      style={style}
    >
      {title && (
        <div className="mb-3 flex items-center gap-2 font-display text-sm font-bold text-text">
          {title}
          {pill && (
            <span className="rounded-full border border-line px-2 py-[2px] font-mono text-[10px] font-normal text-muted">
              {pill}
            </span>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
