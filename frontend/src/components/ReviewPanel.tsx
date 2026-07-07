import { api } from "../api/client";
import type { LoopRunOut } from "../api/types";

export function ReviewPanel({ run, onChange }: { run: LoopRunOut; onChange: () => void }) {
  const act = async (fn: () => Promise<unknown>) => { await fn(); onChange(); };
  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-mono text-xs text-muted uppercase mb-2">纠偏建议</h3>
        <ul className="space-y-2">
          {run.recommendations.map((rec) => (
            <li key={rec.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
              <span className="text-sm"><span className="font-mono text-xs text-muted">[{rec.kind}]</span> {rec.content}</span>
              <span className="flex items-center gap-2 font-mono text-xs">
                {rec.status === "pending" ? (
                  <>
                    <button className="text-good hover:underline" onClick={() => act(() => api.setRecommendationStatus(rec.id, "adopted"))}>采纳</button>
                    <button className="text-alert hover:underline" onClick={() => act(() => api.setRecommendationStatus(rec.id, "rejected"))}>否决</button>
                  </>
                ) : <span className="text-muted">{rec.status}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="font-mono text-xs text-muted uppercase mb-2">起草选题 / 脚本（待审）</h3>
        <ul className="space-y-2">
          {run.drafts.map((d) => (
            <li key={d.id} className="flex items-center justify-between border border-line rounded px-3 py-2">
              <span className="text-sm"><span className="font-mono text-xs text-muted">[{d.kind}]</span> {d.content}</span>
              <span className="flex items-center gap-2 font-mono text-xs">
                {d.review_status === "pending" ? (
                  <>
                    <button className="text-good hover:underline" onClick={() => act(() => api.setDraftStatus(d.id, "adopted"))}>采纳</button>
                    <button className="text-alert hover:underline" onClick={() => act(() => api.setDraftStatus(d.id, "rejected"))}>否决</button>
                  </>
                ) : <span className="text-muted">{d.review_status}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
