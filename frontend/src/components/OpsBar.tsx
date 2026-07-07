import { useState } from "react";
import { api } from "../api/client";
import type { AccountListItem } from "../api/types";

type Toast = { tone: "ok" | "err"; text: string } | null;

/**
 * Ops toolbar: run a batch loop, import snapshots CSV, sync a single account.
 * Reused in the Layout header. `accounts` powers the sync-target picker.
 */
export function OpsBar({
  accounts = [],
  onDone,
}: {
  accounts?: AccountListItem[];
  onDone?: () => void;
}) {
  const [busy, setBusy] = useState<null | "batch" | "import" | "sync">(null);
  const [toast, setToast] = useState<Toast>(null);
  const [showImport, setShowImport] = useState(false);
  const [csv, setCsv] = useState("");
  const [syncId, setSyncId] = useState<number | "">("");

  function flash(t: Toast) {
    setToast(t);
    if (t) window.setTimeout(() => setToast(null), 4000);
  }

  async function runBatch() {
    setBusy("batch");
    try {
      const r = await api.batchRun(true);
      const total = (r?.total ?? r?.accounts ?? "") as string | number;
      flash({ tone: "ok", text: `批量已跑完${total !== "" ? `（${total} 账号）` : ""}` });
      onDone?.();
    } catch (e) {
      flash({ tone: "err", text: String(e) });
    } finally {
      setBusy(null);
    }
  }

  async function doImport() {
    if (!csv.trim()) {
      flash({ tone: "err", text: "请粘贴 CSV 内容" });
      return;
    }
    setBusy("import");
    try {
      const r = await api.importSnapshots(csv);
      const n = (r?.imported ?? r?.count ?? "") as string | number;
      flash({ tone: "ok", text: `导入成功${n !== "" ? `（${n} 行）` : ""}` });
      setShowImport(false);
      setCsv("");
      onDone?.();
    } catch (e) {
      flash({ tone: "err", text: String(e) });
    } finally {
      setBusy(null);
    }
  }

  async function doSync() {
    if (syncId === "") {
      flash({ tone: "err", text: "先选一个账号" });
      return;
    }
    setBusy("sync");
    try {
      await api.syncAccount(Number(syncId));
      flash({ tone: "ok", text: "同步成功" });
      onDone?.();
    } catch (e) {
      // manual-only platforms return 422 "…无自动连接器，请用 CSV 导入"
      const msg = String(e);
      flash({ tone: "err", text: /无自动连接器|CSV/.test(msg) ? "该平台需用 CSV 导入" : msg });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative flex items-center gap-2">
      <select
        value={syncId}
        onChange={(e) => setSyncId(e.target.value === "" ? "" : Number(e.target.value))}
        className="max-w-[130px] rounded-[9px] border border-line bg-panel px-2 py-[6px] font-mono text-[11px] text-text focus:border-cyan focus:outline-none"
        aria-label="选择同步账号"
      >
        <option value="">选账号…</option>
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.handle}
          </option>
        ))}
      </select>
      <button
        onClick={doSync}
        disabled={busy !== null}
        className="rounded-[9px] border border-cyan/50 bg-cyan/[.08] px-3 py-[6px] font-mono text-[11px] text-cyan disabled:opacity-50"
      >
        {busy === "sync" ? "⏳ 同步中…" : "🔌 同步"}
      </button>
      <button
        onClick={() => setShowImport(true)}
        disabled={busy !== null}
        className="rounded-[9px] border border-violet/50 bg-violet/[.08] px-3 py-[6px] font-mono text-[11px] text-violet disabled:opacity-50"
      >
        📥 导入 CSV
      </button>
      <button
        onClick={runBatch}
        disabled={busy !== null}
        className="rounded-[9px] border-none bg-lime px-[14px] py-[6px] font-display text-[12px] font-bold text-[#0A0D12] shadow-[0_4px_18px_rgba(182,255,60,0.25)] disabled:opacity-60"
      >
        {busy === "batch" ? "⏳ 运行中…" : "⚡ 跑一批"}
      </button>

      {toast && (
        <div
          className={`absolute right-0 top-[42px] z-30 max-w-[320px] rounded-lg border px-3 py-2 font-mono text-[11px] ${
            toast.tone === "ok"
              ? "border-good/40 bg-good/[.1] text-good"
              : "border-alert/40 bg-alert/[.1] text-alert"
          }`}
        >
          {toast.text}
        </div>
      )}

      {showImport && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4"
          onClick={() => busy === null && setShowImport(false)}
        >
          <div
            className="w-full max-w-[560px] rounded-2xl border border-line bg-gradient-to-b from-panel2 to-panel p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-display text-sm font-bold text-text">📥 导入快照 CSV</h2>
              <button
                onClick={() => busy === null && setShowImport(false)}
                disabled={busy !== null}
                className="font-mono text-xs text-muted hover:text-text"
              >
                ✕
              </button>
            </div>
            <p className="mb-2 font-mono text-[11px] text-muted">
              粘贴含 platform,handle,ts,followers… 列的 CSV，导入后自动刷新。
            </p>
            <textarea
              value={csv}
              onChange={(e) => setCsv(e.target.value)}
              rows={10}
              placeholder="platform,handle,ts,followers,engagement_rate,..."
              className="w-full resize-y rounded-lg border border-line bg-panel px-3 py-2 font-mono text-[11px] text-text placeholder:text-muted focus:border-lime focus:outline-none"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => setShowImport(false)}
                disabled={busy !== null}
                className="rounded-[9px] border border-line bg-panel px-3 py-[6px] font-mono text-[11px] text-muted disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={doImport}
                disabled={busy !== null}
                className="rounded-[9px] border-none bg-lime px-4 py-[6px] font-display text-[12px] font-bold text-[#0A0D12] disabled:opacity-60"
              >
                {busy === "import" ? "⏳ 导入中…" : "导入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
