export function StatTile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3 rise">
      <div className="font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`font-display text-2xl mt-1 tabnums ${accent ? "text-accent" : "text-text"}`}>{value}</div>
    </div>
  );
}
