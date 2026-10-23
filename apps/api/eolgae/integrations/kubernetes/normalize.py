"""Small allowlisted observations and evidence-backed relationships."""
def text(value, limit=200):
    return str(value or "")[:limit]


def resource(item, kind, observed_at):
    meta, status, spec = item.get("metadata") or {}, item.get("status") or {}, item.get("spec") or {}
    summary = {}
    if kind in {"Deployment", "ReplicaSet"}:
        desired, ready = spec.get("replicas", 1), status.get("readyReplicas", 0)
        summary = {"ready": f"{ready}/{desired}", "observed_generation": text(status.get("observedGeneration"))}
        state = "Ready" if ready == desired and status.get("observedGeneration", 0) >= meta.get("generation", 0) else "Progressing"
    elif kind == "Pod":
        state = text(status.get("phase")) or "Unknown"
        containers = status.get("containerStatuses") or []
        summary = {"ready": f"{sum(bool(c.get('ready')) for c in containers)}/{len(spec.get('containers') or [])}",
                   "restarts": str(sum(c.get("restartCount", 0) for c in containers))}
    elif kind == "Namespace":
        state = text(status.get("phase")) or "Unknown"
    elif kind == "Service":
        state = "Observed"
        summary = {"type": text(spec.get("type"))}
    else:
        state = "Observed"
        summary = {"class": text(spec.get("ingressClassName"))}
    return {"uid": text(meta.get("uid")), "kind": kind, "name": text(meta.get("name")),
            "namespace": text(meta.get("namespace")), "status": state, "summary": summary,
            "observed_at": observed_at, "management": "미확인"}


def relations(raw, items):
    by_uid = {r["uid"]: r for r in items}
    by_name = {(r["kind"], r["namespace"], r["name"]): r for r in items}
    edges, seen = [], set()
    def add(source, target, evidence):
        if source and target and len(edges) < 5000:
            edge = {"source_uid": source["uid"], "target_uid": target["uid"], "evidence": evidence}
            key = (source["uid"], target["uid"], evidence)
            if key not in seen:
                seen.add(key)
                edges.append(edge)
    for kind, obj in raw:
        meta, spec = obj.get("metadata") or {}, obj.get("spec") or {}
        current = by_uid.get(meta.get("uid"))
        if not current:
            continue
        ns = current["namespace"]
        for owner in meta.get("ownerReferences") or []:
            parent = by_uid.get(owner.get("uid"))
            if parent and parent["kind"] == owner.get("kind") and parent["name"] == owner.get("name") and parent["namespace"] == ns:
                add(parent, current, "ownerReference")
        if kind == "Service" and spec.get("selector"):
            selector = spec["selector"]
            for pod_kind, pod in raw:
                pm = pod.get("metadata") or {}
                if pod_kind == "Pod" and pm.get("namespace", "") == ns and all((pm.get("labels") or {}).get(k) == v for k, v in selector.items()):
                    add(current, by_uid.get(pm.get("uid")), "serviceSelector")
        if kind == "Ingress":
            backends = [spec.get("defaultBackend") or {}]
            for rule in spec.get("rules") or []:
                backends.extend(path.get("backend") or {} for path in (rule.get("http") or {}).get("paths") or [])
            for backend in backends:
                name = (backend.get("service") or {}).get("name")
                add(current, by_name.get(("Service", ns, name)), "ingressBackend")
    return edges
