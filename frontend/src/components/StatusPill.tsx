type Status = "running" | "blocked" | "ok" | "error" | "idle";

const MAP: Record<Status, { cls: string; label: string; dot: string }> = {
  running: { cls: "bg-run/14 text-run", label: "生成中", dot: "bg-run" },
  blocked: { cls: "bg-block/14 text-block", label: "待审核", dot: "bg-block" },
  ok: { cls: "bg-ok/14 text-ok", label: "本轮完成", dot: "bg-ok" },
  error: { cls: "bg-err/14 text-err", label: "报错", dot: "bg-err" },
  idle: { cls: "bg-white/8 text-muted2", label: "待命", dot: "bg-muted2" },
};

export function StatusPill({ status, label }: { status: Status; label?: string }) {
  const m = MAP[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold ${m.cls}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
      {label ?? m.label}
    </span>
  );
}
