import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { ChartCard } from "../components/ChartCard";
import { StatTile } from "../components/StatTile";

const PLATFORM_LABEL: Record<string, string> = {
  xiaohongshu: "小红书", douyin: "抖音", tiktok: "TikTok", twitter: "X",
  weixin_video: "视频号", weixin_gzh: "公众号", youtube: "YouTube", instagram: "IG", bilibili: "B站",
};

export function Video() {
  const accounts = useAsync(() => api.listAccounts(), []);
  const usage = useAsync(() => api.getVideoUsage(), []);
  const [acctId, setAcctId] = useState<number | "">("");

  const u = usage.data;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 px-1 pb-4 pt-[10px]">
        <div>
          <h1 className="font-display text-xl font-extrabold tracking-tight text-text">
            视频<span className="text-violet">工作台</span>
          </h1>
          <p className="mt-[3px] font-mono text-[11px] text-muted">
            定调 → 选题 → 脚本 → 视频 → <span className="text-warn">人审成片</span> → 发布 · 每一步人在环
          </p>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 font-mono text-xs text-muted">
          选择账号
          <select
            aria-label="选择账号"
            className="rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text focus:border-violet focus:outline-none"
            value={acctId}
            onChange={(e) => setAcctId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">选择账号…</option>
            {(accounts.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {(PLATFORM_LABEL[a.platform] ?? a.platform)} · {a.handle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* usage panel */}
      <ChartCard title="📊 视频用量" pill={u ? `预算 ${u.caps.video_budget}` : "—"} className="mb-[14px]">
        <div className="grid grid-cols-2 gap-[14px] md:grid-cols-4">
          <StatTile label="今日条数" value={String(u?.today_count ?? 0)} accent />
          <StatTile label="今日成本" value={String(u?.today_cost ?? 0)} />
          <StatTile label="累计条数" value={String(u?.total_count ?? 0)} />
          <StatTile label="累计成本" value={String(u?.total_cost ?? 0)} />
        </div>
        <p className="mt-[10px] font-mono text-[10px] leading-relaxed text-dim">
          日上限:全局 {u?.caps.max_videos_per_day ?? "—"} · 单号 {u?.caps.per_account_per_day ?? "—"} · 单垂类 {u?.caps.per_channel_per_day ?? "—"}
        </p>
      </ChartCard>

      {acctId === "" ? (
        <ChartCard title="👆 先选一个账号">
          <p className="py-8 text-center font-mono text-xs text-muted">选择账号后可设定调、生成脚本/视频、审核成片。</p>
        </ChartCard>
      ) : (
        <div className="grid gap-[14px] lg:grid-cols-2">
          <BriefEditor accountId={acctId} />
          <DraftWorkflow accountId={acctId} onGenerated={() => usage.reload()} />
          <ReviewQueue accountId={acctId} className="lg:col-span-2" />
        </div>
      )}
    </div>
  );
}

// Placeholder sub-components — implemented in Tasks 3-5.
function BriefEditor({ accountId }: { accountId: number }) {
  void accountId;
  return <ChartCard title="🎯 频道定调"><div data-testid="brief-editor" /></ChartCard>;
}
function DraftWorkflow({ accountId, onGenerated }: { accountId: number; onGenerated: () => void }) {
  void accountId; void onGenerated;
  return <ChartCard title="✍️ 选题 · 脚本 · 视频"><div data-testid="draft-workflow" /></ChartCard>;
}
function ReviewQueue({ accountId, className }: { accountId: number; className?: string }) {
  void accountId;
  return <ChartCard title="🎬 成片审核" className={className}><div data-testid="review-queue" /></ChartCard>;
}
