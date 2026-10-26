"use client";
import {useEffect,useRef,useState} from 'react';
import {resourceContext,linkResource,analyzeResource,type Observation,type ObservedResource,type ExecutionContext,type ResourceAnalysis} from '@/lib/resources-api';
const button='rounded border border-[var(--color-border)] px-3 py-2 text-sm disabled:opacity-50';
export function ResourceOperations({resource,data}:{resource:ObservedResource;data:Observation}){
  const [context,setContext]=useState<ExecutionContext|null>(null);
  const [canvas,setCanvas]=useState('');const [analysis,setAnalysis]=useState<ResourceAnalysis|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const mounted=useRef(true);
  const body={observation_id:data.observation_id!,uid:resource.uid,namespace:data.namespace};
  useEffect(()=>{
    mounted.current=true;
    resourceContext(data.target_id,body).then(c=>{if(mounted.current){setContext(c);setCanvas(c.binding?.canvas_id||'');}})
      .catch((e:Error)=>{if(mounted.current)setError(e.message);});
    return()=>{mounted.current=false;};
    // The parent keys this component by target, snapshot and UID.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){if(mounted.current)setError((e as Error).message);}finally{if(mounted.current)setBusy(false);}}
  const signals=data.signals?.filter(s=>s.uid===resource.uid)||[];
  const changes=data.changes?.filter(c=>c.uid===resource.uid)||[];
  return <div className="mt-5 space-y-5 border-t border-[var(--color-border)] pt-4">
    {error&&<p role="alert" className="text-sm text-amber-700">{error}</p>}
    <section aria-label="관측 변경">
      <h3 className="font-semibold">관측 변경</h3>
      <p className="text-xs text-[var(--color-text-muted)]">{data.baseline_at?`${new Date(data.baseline_at).toLocaleString()} 관측과 비교`:'첫 관측 기준선'} · IaC drift 판정이 아닙니다.</p>
      {changes.map((c,i)=><p key={i} className="mt-2 text-sm">{c.type} {c.fields.join(', ')}{c.before&&<span className="block break-all text-xs">{JSON.stringify(c.before)} → {JSON.stringify(c.after)}</span>}</p>)}
      {!changes.length&&<p className="text-sm">확인된 변화 없음 · 불완전한 종류는 비교하지 않습니다.</p>}
    </section>
    <section aria-label="운영 신호">
      <h3 className="font-semibold">운영 신호</h3>
      {data.signal_outcome?.message&&<p className="text-xs text-amber-700">{data.signal_outcome.message}</p>}
      {signals.slice(0,30).map((s,i)=><p key={s.id+String(i)} className="mt-2 break-all text-sm">{s.type} · {s.reason} · {s.count}회<br/><span className="text-xs">{s.source} · {new Date(s.at).toLocaleString()}</span></p>)}
      {!signals.length&&<p className="text-sm">현재 수집 범위의 신호 없음 · 정상 상태를 보장하지 않습니다.</p>}
    </section>
    <section aria-label="실행 이력">
      <h3 className="font-semibold">실행 이력 연결</h3>
      <p className="my-2 text-xs">동일 Target의 Canvas를 직접 연결합니다. 연결된 실행이 이 리소스를 변경했다는 증명은 아닙니다.</p>
      <div className="flex flex-wrap gap-2"><select aria-label="연결할 Canvas" className={`${button} min-w-0 max-w-full`} value={canvas} onChange={e=>setCanvas(e.target.value)}><option value="">연결 없음</option>{context?.candidates.map(c=><option key={c.id} value={c.id}>{c.name} · {c.backend}</option>)}</select>
      <button className={button} disabled={busy||!context} onClick={()=>void action(async()=>{await linkResource(data.target_id,body,canvas||null);const c=await resourceContext(data.target_id,body);if(mounted.current){setContext(c);setAnalysis(null);}})}>연결 저장</button>
      <button className={button} disabled={busy||!context?.binding} onClick={()=>void action(async()=>{const c=await resourceContext(data.target_id,body,true);if(mounted.current)setContext(c);})}>실행 이력 새로고침</button></div>
      {!context?.candidates.length&&<p className="mt-2 text-xs">이 Target에 연결된 소유 Canvas가 없습니다. Canvas 설정에서 Target을 먼저 연결하세요.</p>}
      {context?.binding&&<p className="my-2 break-all text-xs">{context.binding.backend} · Workspace {context.binding.workspace_id||'해당 없음'}</p>}
      {context?.error&&<p role="alert" className="text-sm text-amber-700">{context.error}</p>}
      {context?.runs.map(r=><div key={r.backend+r.id} className="mt-2 break-all rounded border border-[var(--color-border)] p-2 text-sm"><p>{r.operation} · {r.status} · {new Date(r.created_at).toLocaleString()}</p><p className="text-xs">Run {r.id}{r.commit&&` · commit ${r.commit}`}{r.revision&&` · revision ${r.revision}`}</p>{r.url&&<a className="underline" href={r.url} target="_blank" rel="noreferrer">실행 원본 열기</a>}</div>)}
      {context?.binding&&!context.runs.length&&<p className="text-sm">조회된 실행 이력이 없습니다.</p>}
      {context?.has_more&&<p className="text-xs">최근 20개만 표시합니다.</p>}
    </section>
    <section aria-label="근거 기반 분석">
      <h3 className="font-semibold">근거 기반 분석</h3>
      <div className="my-2 flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>void action(async()=>{const a=await analyzeResource(data.target_id,body);if(mounted.current)setAnalysis(a);})}>규칙 분석</button>
      <button className={button} disabled={busy||!analysis?.ai_enabled} onClick={()=>void action(async()=>{const a=await analyzeResource(data.target_id,body,true);if(mounted.current)setAnalysis(a);})}>근거를 AI에 보내 분석</button></div>
      <p className="text-xs text-[var(--color-text-muted)]">AI는 운영자가 활성화한 경우에만 사용합니다. 클릭 시 선택 리소스의 이름·상태·신호·연결 실행 근거를 설정된 LLM 제공자에게 전송합니다. 자동 조치는 없습니다.</p>
      {analysis&&<><p className="my-2 text-xs">{analysis.mode==='ai'?'AI 분석':'규칙 분석'} · {new Date(analysis.observed_at).toLocaleString()} 관측 기준</p>{analysis.warnings.map(w=><p key={w} className="text-xs text-amber-700">{w}</p>)}
      {!analysis.findings.length&&<p className="my-2 text-sm">현재 근거로 제시할 원인 후보가 없습니다.</p>}
      {analysis.findings.map((f,i)=><div key={i} className="my-3 rounded border border-[var(--color-border)] p-3 text-sm"><p className="font-medium">{f.title} · 확신 {f.confidence}</p><p>{f.explanation}</p><ul className="my-2 list-inside list-disc">{f.checks.map(c=><li key={c}>{c}</li>)}</ul><p className="text-xs">근거: {f.evidence_ids.map(id=><a key={id} className="mr-2 underline" href={`#evidence-${id}`}>{id}</a>)}</p></div>)}
      <details className="mt-3"><summary className="cursor-pointer text-sm">분석에 사용한 근거 보기</summary>{analysis.evidence.map(e=><div key={e.id} id={`evidence-${e.id}`} className="my-2"><p className="text-xs font-semibold">{e.id} · {e.type}</p><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded bg-[var(--color-bg-subtle)] p-2 text-xs">{JSON.stringify(e.data,null,2)}</pre></div>)}</details></>}
    </section>
  </div>;
}
