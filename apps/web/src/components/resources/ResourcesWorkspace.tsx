"use client";
import {useEffect,useMemo,useState} from "react";
import Link from "next/link";
import {WorkspaceHeader} from "@/components/WorkspaceShell";
import {useResources} from "@/hooks/useResources";
import {ResourceDetails} from "./ResourceDetails";
const control="min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm";
export function ResourcesWorkspace(){
  const state=useResources();
  const [query,setQuery]=useState("");const [kind,setKind]=useState("");const [selected,setSelected]=useState("");
  useEffect(()=>{setSelected("");setQuery("");setKind("");},[state.targetId,state.namespace]);
  const filtered=useMemo(()=>state.data?.items.filter(r=>(!kind||r.kind===kind)&&`${r.name} ${r.namespace}`.toLowerCase().includes(query.toLowerCase()))||[],[state.data,kind,query]);
  const resource=state.data?.items.find(r=>r.uid===selected);
  const stale=Boolean(state.error)||Boolean(resource&&resource.observed_at!==state.data?.observed_at);
  function select(uid:string){setSelected(uid);setKind("");setQuery("");}
  return <div className="mx-auto max-w-7xl">
    <WorkspaceHeader title="Resources" description="Kubernetes와 AWS 리소스의 상태·변경·실행 근거를 확인합니다."/>
    <div className="mb-4 flex flex-wrap items-end gap-3">
      <label className="grid min-w-[160px] flex-1 gap-1 text-xs">Target<select aria-label="Target" value={state.targetId} onChange={e=>state.changeTarget(e.target.value)} className={control}><option value="">Target 선택</option>{state.targets.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
      <label className="grid min-w-[160px] flex-1 gap-1 text-xs">{state.scope?.label||"범위"}{state.scope?.namespaces.includes("*")?<input aria-label="Namespace" className={control} value={state.namespace} onChange={e=>state.changeNamespace(e.target.value)} placeholder="namespace 또는 * (전체)"/>:<select aria-label="Namespace" className={control} value={state.namespace} onChange={e=>state.changeNamespace(e.target.value)}><option value="">범위 선택</option>{state.scope?.namespaces.map(n=><option key={n}>{n}</option>)}</select>}</label>
      <button className={`${control} disabled:opacity-50`} disabled={!state.scope||!state.namespace||state.loading} onClick={()=>void state.refresh()}>{state.loading?"조회 중…":"새로고침"}</button>
      <Link className="p-2 text-sm underline" href="/targets">Target 연결 관리</Link>
    </div>
    {state.listing||state.scopeLoading?<p role="status">연결 설정을 확인하고 있습니다.</p>:!state.targets.length?<p>연결된 Target이 없습니다. Target 연결 관리에서 추가하세요.</p>:!state.data&&!state.error?<p className="my-4 text-sm">범위를 선택하고 새로고침을 눌러 실제 리소스를 조회하세요.</p>:null}
    {state.error&&<p role="alert" className="my-3 rounded border border-amber-400 p-3 text-sm">{state.error}{state.data&&" · 이전 관측 결과를 표시합니다."}</p>}
    {state.data&&<>
      <div role="status" className="my-4 rounded-lg bg-[var(--color-bg-subtle)] p-3 text-sm">
        <p>{state.data.status==="success"?"조회 완료":state.data.status==="partial"?"일부 조회 실패 또는 불완전한 목록":"조회 실패"} · 범위: {state.data.namespace==="*"?"전체 namespace":state.data.namespace}</p>
        <p className="mt-1 text-xs">마지막 전체 성공: {state.lastSuccess?new Date(state.lastSuccess).toLocaleString():"없음"} · 마지막 시도: {new Date(state.data.observed_at).toLocaleString()}</p>
        {state.data.outcomes.filter(o=>!o.complete).map(o=><p key={o.kind} className="mt-1">{o.kind}: {o.message}</p>)}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label className="text-sm">저장된 관측 <select aria-label="저장된 관측" className={control} disabled={state.loading} value={state.data.observation_id||""} onChange={e=>void state.refresh(e.target.value)}>{state.history.map(h=><option key={h.id} value={h.id}>{new Date(h.observed_at).toLocaleString()} · {h.status}</option>)}</select></label>
        <p className="text-xs">수동 수집 · 범위별 최근 20개 / Target별 100개 · 삭제는 완전한 조회에서만 비교</p>
      </div>
      <details className="mb-4 text-sm"><summary>전체 관측 변경 ({state.data.changes?.length||0})</summary>{state.data.changes?.map((c,i)=><p key={i} className="break-all">{c.type} · {c.kind} / {c.name} {c.fields.join(", ")}</p>)}</details>
      <div className="mb-4 flex flex-wrap gap-2">
        <input aria-label="리소스 검색" placeholder="이름 또는 namespace 검색" className={`${control} flex-1`} value={query} onChange={e=>setQuery(e.target.value)}/>
        <select aria-label="리소스 종류" className={control} value={kind} onChange={e=>setKind(e.target.value)}><option value="">모든 종류</option>{state.data.outcomes.map(o=><option key={o.kind}>{o.kind}</option>)}</select>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(260px,1fr)_minmax(0,1.5fr)]">
        <section aria-label="리소스 목록" className="max-h-[65vh] overflow-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <p className="border-b border-[var(--color-border)] p-3 text-xs">표시 {filtered.length}개 · 조회된 범위 기준</p>
          {filtered.map(r=><button key={r.uid} onClick={()=>select(r.uid)} aria-pressed={r.uid===selected} className={`block w-full border-b border-[var(--color-border)] p-3 text-left text-sm ${r.uid===selected?"bg-[var(--color-bg-subtle)]":""}`}><span className="block break-all font-medium">{r.name}</span><span className="block text-xs text-[var(--color-text-muted)]">{r.namespace||"Cluster"} / {r.kind} · {r.status}{state.error||r.observed_at!==state.data?.observed_at?" · 이전 관측":""}</span></button>)}
          {!filtered.length&&<p className="p-4 text-sm">{state.data.complete&&!state.error?(query||kind?"검색 조건에 맞는 리소스가 없습니다.":"조회한 범위에 리소스가 없습니다."):"조회가 완전하지 않아 리소스 유무를 확정할 수 없습니다."}</p>}
        </section>
        {resource?<ResourceDetails resource={resource} data={state.data} select={select} stale={stale}/>:<p className="p-5 text-sm text-[var(--color-text-muted)]">리소스를 선택하면 상태와 관계를 볼 수 있습니다.</p>}
      </div>
    </>}
  </div>;
}
