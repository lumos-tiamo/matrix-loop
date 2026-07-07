export function ScoreBar({ score }: { score: number | null }) {
  if (score == null) return <span className="font-mono text-muted text-xs">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded bg-line overflow-hidden">
        <div className="h-full rounded bg-accent" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
      <span className="font-mono text-sm tabnums">{score.toFixed(0)}</span>
    </div>
  );
}
