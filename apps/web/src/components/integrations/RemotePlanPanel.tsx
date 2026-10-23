"use client";

import { useEffect, useState } from "react";
import { boundCanvases } from "@/lib/remote-plans-api";
import { useRemotePlans } from "@/hooks/useRemotePlans";

const statusLabel: Record<string, string> = {
  submitting:"제출 확인 중", unknown:"결과 확인 필요", pending:"대기", running:"실행 중",
  success:"Plan 완료", failed:"실패", cancelled:"취소",
};

export function RemotePlanPanel({workspaceId, revision}: {workspaceId:string; revision:number}) {
  const [canvases, setCanvases] = useState<{id:string;name:string}[]>([]);
  const [canvasId, setCanvasId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setCanvasId(""); setCanvases([]); setError("");
    boundCanvases(workspaceId).then((result) => {
      if (active) { setCanvases(result.items); setCanvasId(result.items[0]?.id || ""); }
    }).catch((e:Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [workspaceId, revision]);
  return <section className="mt-6 border-t pt-4">
    <h3 className="font-semibold">Git commit Plan 요청</h3>
    <p className="my-2 text-sm text-[var(--color-text-muted)]">연결된 Workspace의 Git commit으로 Plan만 실행합니다. Canvas는 참조 버전으로 기록되며 HCL을 전송하지 않습니다. Apply와 승인은 Terrakube에서 별도로 진행합니다.</p>
    {error && <p role="alert">{error}</p>}
    {canvases.length ? <><label className="text-sm">연결된 Canvas<select aria-label="Plan 대상 Canvas" className="my-2 w-full rounded border bg-[var(--color-surface)] p-2" value={canvasId} onChange={(e) => setCanvasId(e.target.value)}>{canvases.map((canvas) => <option key={canvas.id} value={canvas.id}>{canvas.name}</option>)}</select></label>
      {canvasId && <PlanRequests key={canvasId} canvasId={canvasId} />}</> : <p className="text-sm">내 계정의 연결된 Canvas가 없습니다. 위에서 실행 이력이 없는 설계를 연결하세요.</p>}
  </section>;
}

function PlanRequests({canvasId}: {canvasId:string}) {
  const state = useRemotePlans(canvasId);
  const [commit, setCommit] = useState("");
  const valid = /^[0-9a-f]{40}$/.test(commit);
  return <div className="space-y-3">
    {state.data?.plan_enabled ? <>
      <label className="block text-sm">Git commit SHA (40자리)<input aria-label="Git commit SHA" className="mt-1 w-full rounded border bg-[var(--color-surface)] p-2 font-mono" value={state.pending?.commit_sha || commit} disabled={Boolean(state.pending) || state.busy} onChange={(e) => setCommit(e.target.value.trim().toLowerCase())} placeholder="실행할 commit의 전체 SHA" /></label>
      <button disabled={state.busy || (!state.pending && (!valid || Boolean(state.active)))} onClick={() => void state.submit(commit)} className="rounded border px-3 py-2 text-sm disabled:opacity-50">{state.pending ? "동일 요청 확인" : "이 commit으로 Plan 요청"}</button>
      {state.pending && !state.active && <button className="ml-2 text-sm underline" disabled={state.busy} onClick={state.discardRejectedRequest}>입력 다시 준비</button>}
    </> : <p className="text-sm">Plan 제출은 비활성입니다. 서버의 Plan 기능과 사용자 허용 목록을 확인하세요.</p>}
    {state.error && <p role="alert" className="break-words text-sm text-[var(--color-danger)]">{state.error}</p>}
    {state.active && <p role="status" className="text-sm">진행 중인 요청을 5초마다 확인합니다. 불확실한 요청은 재전송하지 않습니다.</p>}
    {state.data?.items.length === 0 && <p className="text-sm">Eolgae에서 요청한 Plan이 없습니다.</p>}
    {state.data?.items.map((plan) => <article key={plan.id} className="space-y-2 rounded border p-3 text-sm">
      <div className="flex flex-wrap justify-between gap-2"><strong>{statusLabel[plan.status] || plan.status}{plan.job_id && ` · Run #${plan.job_id}`}</strong><button disabled={state.busy} onClick={() => void state.sync(plan.id)} className="underline disabled:opacity-50">상태 확인</button></div>
      <p className="break-all font-mono">commit: {plan.commit_sha}</p>
      <p className="break-all text-xs text-[var(--color-text-muted)]">Canvas 참조 버전: {plan.canvas_version_id}</p>
      <p className="text-xs">마지막 확인: {new Date(plan.updated_at).toLocaleString()}</p>
      {plan.stale && <p>현재 Canvas와 다른 참조 버전의 결과입니다.</p>}
      {plan.result && <p>원격 상태: {plan.result.remote_status}{typeof plan.result.has_changes === "boolean" && ` · ${plan.result.has_changes ? "변경 있음" : "변경 없음"}`}</p>}
      {plan.error_message && <p role="status" className="break-words">{plan.error_message}</p>}
      {plan.result?.url && <a className="inline-block underline" href={plan.result.url} target="_blank" rel="noreferrer">Terrakube에서 상세 Plan 보기</a>}
    </article>)}
  </div>;
}
