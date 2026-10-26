import {ResourceOperations} from "./ResourceOperations";
import type {Observation,ObservedResource} from "@/lib/resources-api";
const evidence:Record<string,string>={ownerReference:"소유 관계 · ownerReference",serviceSelector:"연관 관계 · Service selector",ingressBackend:"연관 관계 · Ingress backend",awsVpc:"VPC 소속",awsSubnet:"Subnet 소속",awsSecurityGroup:"Security Group 연결"};
export function ResourceDetails({resource,data,select,stale}:{resource:ObservedResource;data:Observation;select:(uid:string)=>void;stale:boolean}){
  const links=data.relations.filter(r=>r.source_uid===resource.uid||r.target_uid===resource.uid);
  return <section aria-label="리소스 상세" className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
    <p className="text-xs text-[var(--color-text-muted)]">{resource.namespace||"Cluster"} / {resource.kind}</p>
    <h2 className="my-2 break-all text-xl font-semibold">{resource.name}</h2>
    {stale&&<p role="status" className="my-2 text-amber-700">이전 관측 결과입니다. 현재 상태를 확인하지 못했습니다.</p>}
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      <dt>관측 상태</dt><dd>{resource.status}</dd><dt>관측 시각</dt><dd>{new Date(resource.observed_at).toLocaleString()}</dd>
      <dt>관리 주체</dt><dd>{resource.management}</dd>
      {Object.entries(resource.summary).map(([key,value])=><div key={key} className="contents"><dt>{key}</dt><dd className="break-all">{value||"미확인"}</dd></div>)}
    </dl>
    <h3 className="mb-2 mt-6 font-semibold">관계</h3>
    <p className="mb-3 text-xs text-[var(--color-text-muted)]">조회된 리소스 사이의 근거만 표시합니다. selector 일치는 트래픽 성공을 보장하지 않습니다.</p>
    {!data.relations_complete&&<p className="text-sm text-amber-700">관계 개수 제한으로 일부만 표시됩니다.</p>}
    <ul className="space-y-2">{links.map(link=>{
      const outgoing=link.source_uid===resource.uid;
      const other=data.items.find(r=>r.uid===(outgoing?link.target_uid:link.source_uid));
      return other&&<li key={`${link.source_uid}:${link.target_uid}:${link.evidence}`}><button onClick={()=>select(other.uid)} className="w-full rounded border border-[var(--color-border)] p-3 text-left text-sm hover:bg-[var(--color-bg-subtle)]"><span className="block break-all">{outgoing?"→":"←"} {other.kind} / {other.name}</span><span className="text-xs text-[var(--color-text-muted)]">{evidence[link.evidence]||link.evidence}</span></button></li>;
    })}</ul>
    {!links.length&&<p className="text-sm">현재 조회 범위에서 확인된 관계가 없습니다.</p>}
    {data.observation_id&&<ResourceOperations key={`${data.target_id}:${data.observation_id}:${resource.uid}`} resource={resource} data={data}/>}
  </section>;
}
