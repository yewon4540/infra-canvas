"use client";

import { useEffect, useState } from "react";
import { RemotePlanPanel } from "@/components/integrations/RemotePlanPanel";
import { WorkspaceHeader, WorkspaceShell } from "@/components/WorkspaceShell";
import { listCanvases, type Canvas } from "@/lib/api";
import {
  bindRemoteWorkspace, getExecutionCapabilities, getRemoteJobs, getRemoteWorkspaces,
  type ExecutionCapabilities, type RemoteJob, type RemoteWorkspace,
} from "@/lib/execution-api";

export default function IntegrationsPage() {
  const [capabilities, setCapabilities] = useState<ExecutionCapabilities | null>(null);
  const [workspaces, setWorkspaces] = useState<RemoteWorkspace[]>([]);
  const [selected, setSelected] = useState("");
  const [jobs, setJobs] = useState<RemoteJob[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [canvasId, setCanvasId] = useState("");
  const [error, setError] = useState("");
  const [jobError, setJobError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [binding, setBinding] = useState(false);
  const [revision, setRevision] = useState(0);
  const [bindingRevision, setBindingRevision] = useState(0);
  const [observedAt, setObservedAt] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setSelected(""); setWorkspaces([]);
    getExecutionCapabilities().then(async (cap) => {
      if (!active) return;
      setCapabilities(cap);
      if (cap.terrakube && cap.terrakube_configured) {
        const remote = await getRemoteWorkspaces();
        if (!active) return;
        setWorkspaces(remote.items);
        setError(remote.errors.map((item) => `${item.workspace_id}: ${item.message}`).join(" / "));
        setObservedAt(new Date().toLocaleString());
        setSelected(remote.items[0]?.id || "");
        const available = await listCanvases();
        if (active) setCanvases(available.filter((canvas) => canvas.state === "design"));
      }
    }).catch((e: Error) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);

  useEffect(() => {
    let active = true;
    setJobs([]); setJobError(""); setHasMore(false); setJobsLoading(Boolean(selected));
    if (selected) getRemoteJobs(selected).then((result) => {
      if (active) { setJobs(result.items); setHasMore(result.has_more); }
    }).catch((e: Error) => { if (active) setJobError(e.message); })
      .finally(() => { if (active) setJobsLoading(false); });
    return () => { active = false; };
  }, [selected]);

  async function connect() {
    setBinding(true); setMessage("");
    try {
      await bindRemoteWorkspace(canvasId, selected);
      setMessage("연결했습니다. 이 Canvas의 직접 실행은 차단됩니다.");
      setBindingRevision((value) => value + 1);
    } catch (e) { setMessage((e as Error).message); }
    finally { setBinding(false); }
  }

  return (
    <WorkspaceShell active="settings">
      <div className="mx-auto max-w-5xl space-y-5">
        <WorkspaceHeader title="실행 및 Terrakube 연동" description="실행 기능과 외부 Workspace의 실행 이력을 확인합니다." />
        <section className="rounded-md border border-[var(--color-border)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">이 설치의 기능</h2>
            <button className="rounded border px-3 py-1.5 text-sm disabled:opacity-50" disabled={loading || binding} onClick={() => setRevision((value) => value + 1)}>새로고침</button>
          </div>
          <p className="mt-3 text-sm">직접 실행: {capabilities ? capabilities.direct_execution ? "활성" : "비활성 · 조회와 설계 가능" : "확인 중"}</p>
          <p className="mt-2 text-sm">Terrakube: {capabilities ? capabilities.terrakube ? capabilities.terrakube_configured ? (capabilities.terrakube_operations.includes("plan") ? "연결 설정됨 · Plan 요청 가능" : "연결 설정됨 · 조회 전용") : "연결 설정 필요" : "미사용 또는 조회 권한 없음" : "확인 중"}</p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">실행과 승인은 Terrakube에서 진행합니다. 허용된 계정은 아래에서 Plan만 요청할 수 있습니다.</p>
        </section>
        {error && <p role="alert" className="break-words text-sm text-[var(--color-danger)]">{error}</p>}
        {loading && <p role="status">연결 확인 중…</p>}
        {capabilities?.terrakube && capabilities.terrakube_configured && !loading && (
          <section className="rounded-md border border-[var(--color-border)] p-5">
            <h2 className="font-semibold">허용된 Workspace</h2>
            <p className="my-2 text-xs text-[var(--color-text-muted)]">마지막 조회: {observedAt || "미확인"}</p>
            {workspaces.length > 0 ? <select aria-label="Workspace" className="w-full rounded border bg-[var(--color-surface)] p-2" value={selected} onChange={(event) => setSelected(event.target.value)}>
              {workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name} · {workspace.branch || "branch 미확인"}</option>)}
            </select> : <p>조회 가능한 Workspace가 없습니다. 위 연결 오류와 서버 설정을 확인하세요.</p>}
            {workspaces.find((item) => item.id === selected)?.url && <a className="mt-3 inline-block text-sm underline" href={workspaces.find((item) => item.id === selected)?.url || ""} target="_blank" rel="noreferrer">Terrakube에서 Workspace 열기</a>}
            <h3 className="mb-2 mt-5 font-medium">최근 실행</h3>
            {jobsLoading ? <p role="status">실행 이력 조회 중…</p> : jobError ? <p role="alert" className="text-sm text-[var(--color-danger)]">{jobError}</p> : jobs.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
              <thead><tr><th className="p-2">Run</th><th className="p-2">원격 상태</th><th className="p-2">실행 commit</th></tr></thead>
              <tbody>{jobs.map((job) => <tr className="border-t" key={job.id}><td className="p-2">{job.url ? <a href={job.url} target="_blank" rel="noreferrer" className="underline">#{job.id}</a> : `#${job.id}`}</td><td className="p-2">{job.status}</td><td className="p-2">{job.commit || "미확인"}</td></tr>)}</tbody>
            </table></div> : selected ? <p className="text-sm">이 Workspace에 조회된 실행이 없습니다.</p> : null}
            {hasMore && <p className="mt-2 text-xs">최근 20건을 표시합니다. 전체 이력은 Terrakube에서 확인하세요.</p>}
            {selected && <div className="mt-6 border-t pt-4">
              <h3 className="font-medium">설계 Canvas 연결</h3>
              <p className="my-2 text-sm text-[var(--color-text-muted)]">실행 이력이 없는 설계만 연결할 수 있습니다. 연결 후 직접 실행과 다른 Workspace로의 전환이 차단됩니다. IaC 코드나 State를 전송하지 않습니다.</p>
              <div className="flex flex-wrap gap-2"><select aria-label="Canvas" className="min-w-0 flex-1 rounded border bg-[var(--color-surface)] p-2" value={canvasId} onChange={(event) => setCanvasId(event.target.value)}><option value="">연결할 Canvas 선택</option>{canvases.map((canvas) => <option key={canvas.id} value={canvas.id}>{canvas.name}</option>)}</select>
                <button disabled={!canvasId || binding} className="rounded border px-3 py-2 text-sm disabled:opacity-50" onClick={connect}>{binding ? "연결 중…" : "Workspace에 연결"}</button></div>
              {message && <p role="status" className="mt-2 text-sm">{message}</p>}
            </div>}
            {selected && <RemotePlanPanel key={selected} workspaceId={selected} revision={bindingRevision} />}
          </section>
        )}
      </div>
    </WorkspaceShell>
  );
}
