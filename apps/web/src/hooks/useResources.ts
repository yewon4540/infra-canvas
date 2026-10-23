"use client";
import {useEffect,useRef,useState} from "react";
import {listTargets,type Target} from "@/lib/api";
import {getResourceScope,getResources,type Observation,type ResourceScope} from "@/lib/resources-api";

export function useResources() {
  const [targets,setTargets]=useState<Target[]>([]);
  const [targetId,setTargetId]=useState("");
  const [namespace,setNamespace]=useState("");
  const [scope,setScope]=useState<ResourceScope|null>(null);
  const [data,setData]=useState<Observation|null>(null);
  const [lastSuccess,setLastSuccess]=useState<string|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [listing,setListing]=useState(true);
  const [scopeLoading,setScopeLoading]=useState(false);
  const generation=useRef(0);
  const mounted=useRef(true);
  useEffect(()=>{
    mounted.current=true;
    listTargets().then(items=>{
      if (!mounted.current) return;
      const valid=items.filter(t=>t.kind==="kubernetes_cluster"&&!t.archived_at);
      setTargets(valid);setTargetId(valid[0]?.id||"");
    }).catch((e:Error)=>{if(mounted.current)setError(e.message);})
      .finally(()=>{if(mounted.current)setListing(false);});
    return ()=>{mounted.current=false;generation.current++;};
  },[]);
  useEffect(()=>{
    const current=++generation.current;
    setData(null);setLastSuccess(null);setScope(null);setNamespace("");setLoading(false);setError("");
    if(!targetId){setScopeLoading(false);return;}
    setScopeLoading(true);
    getResourceScope(targetId).then(s=>{
      if(current!==generation.current||!mounted.current)return;
      setScope(s);setNamespace(s.default_namespace);
    }).catch((e:Error)=>{if(current===generation.current&&mounted.current)setError(e.message);})
      .finally(()=>{if(current===generation.current&&mounted.current)setScopeLoading(false);});
  },[targetId]);
  function changeNamespace(value:string){
    generation.current++;setNamespace(value);setData(null);setLastSuccess(null);setError("");setLoading(false);
  }
  function changeTarget(value:string){generation.current++;setTargetId(value);setData(null);setScope(null);setError("");setLastSuccess(null);}
  async function refresh(){
    if(!scope||loading||!namespace)return;
    const current=++generation.current;
    setLoading(true);setError("");
    try{
      const result=await getResources(targetId,namespace);
      if(current!==generation.current||!mounted.current)return;
      // Preserve only observations for failed kinds in this exact target/scope.
      setData(previous=>{
        const failed=new Set(result.outcomes.filter(o=>o.status==="error").map(o=>o.kind));
        const old=previous?.items.filter(r=>failed.has(r.kind))||[];
        return {...result,items:[...result.items,...old]};
      });
      if(result.complete)setLastSuccess(result.observed_at);
    }catch(e){if(current===generation.current&&mounted.current)setError((e as Error).message);}
    finally{if(current===generation.current&&mounted.current)setLoading(false);}
  }
  return {targets,targetId,namespace,scope,data,lastSuccess,error,loading,listing,scopeLoading,changeTarget,changeNamespace,refresh};
}
