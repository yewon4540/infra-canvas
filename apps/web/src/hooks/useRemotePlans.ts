import { useCallback, useEffect, useRef, useState } from "react";
import {
  activeRemotePlan, listRemotePlans, submitRemotePlan, syncRemotePlan,
  type RemotePlanList, type RemotePlanRequest,
} from "@/lib/remote-plans-api";

export function useRemotePlans(canvasId: string) {
  const [data, setData] = useState<RemotePlanList | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<RemotePlanRequest | null>(null);
  const working = useRef(false);
  const current = useRef(canvasId);
  current.current = canvasId;
  const storageKey = `eolgae.remote-plan.${canvasId}`;

  const refresh = useCallback(async () => {
    const result = await listRemotePlans(canvasId);
    if (current.current === canvasId) setData(result);
  }, [canvasId]);

  useEffect(() => {
    setData(null); setError(""); setPending(null);
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) setPending(JSON.parse(saved) as RemotePlanRequest);
    } catch { setError("이전 요청을 복원하지 못했습니다. 이력을 확인하세요."); }
    if (canvasId) refresh().catch((e: Error) => { if (current.current === canvasId) setError(e.message); });
  }, [canvasId, refresh, storageKey]);

  const sync = useCallback(async (planId: string) => {
    if (working.current) return;
    working.current = true; setBusy(true);
    try {
      await syncRemotePlan(canvasId, planId);
      await refresh();
      if (current.current === canvasId) setError("");
    } catch (e) { if (current.current === canvasId) setError((e as Error).message); }
    finally { working.current = false; setBusy(false); }
  }, [canvasId, refresh]);

  const active = data?.items.find((item) => activeRemotePlan(item.status));
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => { void sync(active.id); }, 5000);
    return () => clearInterval(timer);
  }, [active?.id, sync]);

  async function submit(commit: string) {
    if (!data || working.current) return;
    working.current = true; setBusy(true); setError("");
    const body = pending || {idempotency_key:crypto.randomUUID(), commit_sha:commit, canvas_revision:data.canvas_revision};
    try {
      // Persist before sending; a browser timeout/reload must reuse the same request.
      sessionStorage.setItem(storageKey, JSON.stringify(body)); setPending(body);
      await submitRemotePlan(canvasId, body);
      sessionStorage.removeItem(storageKey);
      if (current.current === canvasId) setPending(null);
      await refresh();
    } catch (e) { if (current.current === canvasId) setError((e as Error).message); }
    finally { working.current = false; setBusy(false); }
  }

  function discardRejectedRequest() {
    // Does not resubmit or unlock a server-side unknown request.
    sessionStorage.removeItem(storageKey); setPending(null); setError("");
    void refresh().catch((e: Error) => setError(e.message));
  }
  return {data, error, busy, pending, active, refresh, sync, submit, discardRejectedRequest};
}
