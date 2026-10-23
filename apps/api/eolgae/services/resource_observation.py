"""Stateless manual observation; no raw Kubernetes objects or credentials persisted."""
from datetime import datetime, timezone
from eolgae.integrations.kubernetes.access import access_for
from eolgae.integrations.kubernetes.client import KINDS, Reader, ReadError
from eolgae.integrations.kubernetes.normalize import resource, relations


def observe(target, namespace=None):
    access = access_for(target, namespace)
    observed_at = datetime.now(timezone.utc).isoformat()
    raw, items, outcomes = [], [], []
    with Reader(access) as reader:
        for kind in KINDS:
            try:
                values, complete = reader.collect(kind)
                normalized = [resource(value, kind, observed_at) for value in values]
                if any(not r["uid"] or not r["name"] for r in normalized):
                    raise ReadError("invalid_response", "리소스 식별자 누락")
                raw.extend((kind, value) for value in values)
                items.extend(normalized)
                outcomes.append({"kind": kind, "status": "success" if complete else "incomplete",
                                 "complete": complete, "count": len(values),
                                 "message": "" if complete else "페이지 제한: 일부 목록만 조회됨"})
            except (TypeError, ValueError, AttributeError, KeyError):
                outcomes.append({"kind": kind, "status": "error", "complete": False,
                                 "count": 0, "code": "invalid_response", "message": "Kubernetes 리소스 형식 오류"})
            except ReadError as error:
                outcomes.append({"kind": kind, "status": "error", "complete": False,
                                 "count": 0, "code": error.code, "message": error.message})
    complete = all(o["complete"] for o in outcomes)
    any_success = any(o["status"] != "error" for o in outcomes)
    edges = relations(raw, items)
    return {"relations_complete": len(edges) < 5000, "target_id": str(target.id), "namespace": access.namespace, "observed_at": observed_at,
            "status": "success" if complete else "partial" if any_success else "error",
            "complete": complete, "items": items, "relations": edges, "outcomes": outcomes}
