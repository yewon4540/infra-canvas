"use client";
import {useEffect,useRef,useState} from "react";
import {listTargets,type Target} from "@/lib/api";
import {getResourceScope,collectObservation,savedObservations,loadObservation,type Observation,type ResourceScope,type ObservationHistory} from "@/lib/resources-api";

export function useResources(){
  const [targets,setTargets]=useState<Target[]>([]);
  const [targetId,setTargetId]=useState("");const [namespace,setNamespace]=useState("");
  const [scope,setScope]=useState<ResourceScope|null>(null);
  const [data,setData]=useState<Observation|null>(null);
  const [history,setHistory]=useState<ObservationHistory[]>([]);
  const [error,setError]=useState("");const [loading,setLoading]=useState(false);
  const [listing,setListing]=useState(true);const [scopeLoading,setScopeLoading]=useState(false);
  const generation=useRef(0);const scopeGeneration=useRef(0);const mounted=useRef(true);
  useEffect(()=>{
    mounted.current=true;
    listTargets().then(items=>{if(mounted.current){const valid=items.filter(t=>!t.archived_at);setTargets(valid);setTargetId(valid[0]?.id||"");}})
      .catch((e:Error)=>{if(mounted.current)setError(e.message);}).finally(()=>{if(mounted.current)setListing(false);});
    return()=>{mounted.current=false;generation.current++;scopeGeneration.current++;};
  },[]);
  useEffect(()=>{
    const version=++scopeGeneration.current;
    setScope(null);setData(null);setHistory([]);setNamespace("");setError("");setLoading(false);
    if(!targetId){setScopeLoading(false);return;}
    setScopeLoading(true);
    getResourceScope(targetId).then(s=>{if(version===scopeGeneration.current&&mounted.current){setScope(s);setNamespace(s.default_namespace);}})
      .catch((e:Error)=>{if(version===scopeGeneration.current&&mounted.current)setError(e.message);})
      .finally(()=>{if(version===scopeGeneration.current&&mounted.current)setScopeLoading(false);});
  },[targetId]);
  useEffect(()=>{
    const version=++generation.current;
    setData(null);setHistory([]);
    if(!scope||!namespace)return;
    setLoading(true);
    savedObservations(targetId,namespace).then(result=>{if(version===generation.current&&mounted.current){setData(result.latest);setHistory(result.history);}})
      .catch((e:Error)=>{if(version===generation.current&&mounted.current)setError(e.message);})
      .finally(()=>{if(version===generation.current&&mounted.current)setLoading(false);});
  },[targetId,namespace,scope]);
  function changeNamespace(value:string){generation.current++;setNamespace(value);setData(null);setHistory([]);setError("");setLoading(false);}
  function changeTarget(value:string){generation.current++;setTargetId(value);setScope(null);setData(null);setHistory([]);setError("");}
  async function refresh(snapshot?:string){
    if(!scope||loading||!namespace)return;
    const version=++generation.current;setLoading(true);setError("");
    try{
      const result=snapshot?await loadObservation(targetId,namespace,snapshot):await collectObservation(targetId,namespace);
      if(version!==generation.current||!mounted.current)return;
      setData(result);
      const saved=await savedObservations(targetId,namespace);
      if(version===generation.current&&mounted.current)setHistory(saved.history);
    }catch(e){if(version===generation.current&&mounted.current)setError((e as Error).message);}
    finally{if(version===generation.current&&mounted.current)setLoading(false);}
  }
  return {targets,targetId,namespace,scope,data,history,lastSuccess:data?.last_success_at,error,loading,listing,scopeLoading,changeTarget,changeNamespace,refresh};
}
