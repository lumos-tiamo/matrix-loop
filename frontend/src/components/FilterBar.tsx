export type SortKey = "score" | "followers";

export interface PlatformChip {
  value: string; // "" == 全部
  label: string;
}

export function FilterBar({
  search,
  onSearch,
  platform,
  onPlatform,
  chips,
  sort,
  onSort,
  onRunBatch,
  running,
}: {
  search: string;
  onSearch: (v: string) => void;
  platform: string;
  onPlatform: (v: string) => void;
  chips: PlatformChip[];
  sort: SortKey;
  onSort: (v: SortKey) => void;
  onRunBatch: () => void;
  running: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-1 pb-4 pt-[10px]">
      <span className="font-display text-[13px] font-bold text-muted">总览大屏</span>
      <div className="flex-1" />
      <input
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="🔍 搜索账号 / 垂类…"
        className="min-w-[220px] rounded-[9px] border border-line bg-panel px-3 py-[7px] font-mono text-xs text-text placeholder:text-muted focus:border-lime focus:outline-none"
      />
      {chips.map((c) => {
        const on = platform === c.value;
        return (
          <button
            key={c.value || "all"}
            onClick={() => onPlatform(c.value)}
            className={`rounded-full border px-3 py-[5px] font-mono text-[11px] ${
              on ? "border-lime bg-lime/[.08] text-lime" : "border-line bg-panel text-muted"
            }`}
          >
            {c.label}
          </button>
        );
      })}
      <button
        onClick={() => onSort(sort === "score" ? "followers" : "score")}
        className="rounded-full border border-line bg-panel px-3 py-[5px] font-mono text-[11px] text-muted"
        title="切换排序"
      >
        ⇅ {sort === "score" ? "价值分" : "粉丝"}
      </button>
      <button
        onClick={onRunBatch}
        disabled={running}
        className="rounded-[9px] border-none bg-lime px-[14px] py-2 font-display text-[13px] font-bold text-[#0A0D12] shadow-[0_4px_18px_rgba(182,255,60,0.25)] disabled:opacity-60"
      >
        {running ? "⏳ 运行中…" : "⚡ 跑一批"}
      </button>
    </div>
  );
}
