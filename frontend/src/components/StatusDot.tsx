const MAP: Record<string, { color: string; label: string }> = {
  ok: { color: "#3ECF8E", label: "正常" },
  no_progress: { color: "#F5A524", label: "需介入" },
  error: { color: "#F0526B", label: "错误" },
  budget_stop: { color: "#F0526B", label: "超预算" },
};
export function StatusDot({ status }: { status: string | null }) {
  const s = (status && MAP[status]) || { color: "#8B93A7", label: status ?? "未跑" };
  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs">
      <span className="h-2 w-2 rounded-full" style={{ background: s.color, boxShadow: `0 0 8px ${s.color}` }} />
      {s.label}
    </span>
  );
}
