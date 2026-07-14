import type { ReactNode } from "react";

/** Frosted-glass card surface (replaces ChartCard, keeps title/pill/children API). */
export function GlassCard({
  title,
  pill,
  children,
  className = "",
}: {
  title?: string;
  pill?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`glass p-4 ${className}`}>
      {(title || pill) && (
        <div className="flex items-center gap-2 mb-3">
          {title && <h3 className="text-[13px] font-semibold text-txt">{title}</h3>}
          {pill && <span className="ml-auto">{pill}</span>}
        </div>
      )}
      {children}
    </div>
  );
}
