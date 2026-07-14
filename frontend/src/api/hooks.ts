import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const run = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then((d) => { setData(d); setUpdatedAt(Date.now()); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(); }, [run]);

  // Opt-in auto-refresh: silently re-fetch on an interval so the dashboard stays live
  // (keeps the last good data on transient errors instead of flashing a spinner).
  useEffect(() => {
    if (!pollMs) return;
    const t = setInterval(() => {
      fn().then((d) => { setData(d); setUpdatedAt(Date.now()); }).catch(() => { /* keep last good */ });
    }, pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, pollMs]);

  return { data, error, loading, reload: run, updatedAt };
}
