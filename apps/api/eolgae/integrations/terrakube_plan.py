"""Pinned Plan-only submission; remote writes are deliberately limited to job POST."""
import base64
import binascii
import hashlib
from uuid import UUID

import httpx
from fastapi import HTTPException

from eolgae.config import settings
from eolgae.integrations import terrakube as tk

# Only the stock, single-step template is supported. Never execute commands/imports
# embedded in a configurable template. Snapshot this body to avoid template TOCTOU.
PLAN_TCL = 'flow:\n  - type: "terraformPlan"\n    name: "Plan"\n    step: 100'
PLAN_DIGEST = hashlib.sha256(PLAN_TCL.encode()).hexdigest()


class SubmissionUncertain(Exception):
    """A request may have reached Terrakube. Never resend it automatically."""


def plan_allowed(user_id) -> bool:
    return (tk.authorized(user_id) and settings.terrakube_plan_enabled
            and str(user_id) in tk.identifiers(settings.terrakube_plan_user_ids)
            and bool(settings.terrakube_plan_template_id))


def require_plan_access(user_id, workspace_id):
    tk.require_access(user_id, workspace_id)
    if not plan_allowed(user_id):
        raise HTTPException(403, "Terrakube Plan 제출 권한이 없습니다.")


def valid_tcl(value) -> bool:
    try:
        return isinstance(value, str) and base64.b64decode(value, validate=True).decode().strip() == PLAN_TCL
    except (ValueError, UnicodeError, binascii.Error):
        return False


def approved_template() -> str:
    try:
        template_id = str(UUID(settings.terrakube_plan_template_id))
    except ValueError:
        raise HTTPException(503, "Plan 템플릿 UUID 설정이 필요합니다.") from None
    data = tk.request(f"/organization/{tk._organization()}/template/{template_id}")["data"]
    if (not isinstance(data, dict) or str(data.get("id")) != template_id
            or not valid_tcl((data.get("attributes") or {}).get("tcl"))):
        raise HTTPException(409, "허용 템플릿이 표준 단일 Plan과 다릅니다. 제출을 차단했습니다.")
    return template_id


def marker(request_id) -> str:
    return f"eolgae:plan:{request_id}"


def submit(plan) -> str:
    # templateReference is intentionally omitted: Terrakube resolves it later and
    # could execute a changed template. The validated immutable TCL is sent inline.
    body = {"data": {"type": "job", "attributes": {
        "tcl": base64.b64encode(PLAN_TCL.encode()).decode(),
        "overrideBranch": plan.workspace_snapshot["execution_ref"],
        "commitId": plan.commit_sha, "comments": marker(plan.id),
    }, "relationships": {"workspace": {"data": {"type": "workspace", "id": plan.workspace_id}}}}}
    auth = tk.headers()
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(f"{plan.api_url}/organization/{plan.organization_id}/job",
                                   json=body, headers={**auth, "Content-Type": "application/vnd.api+json"})
        if 400 <= response.status_code < 500:
            raise HTTPException(502, "Terrakube가 Plan 제출을 거절했습니다. 원격 권한과 설정을 확인하세요.")
        if not 200 <= response.status_code < 300:
            raise SubmissionUncertain()
        data = response.json().get("data")
        if not isinstance(data, dict) or not str(data.get("id", "")).isdigit():
            raise SubmissionUncertain()
        return str(data["id"])
    except (httpx.HTTPError, ValueError, AttributeError):
        raise SubmissionUncertain() from None


def lookup(plan) -> dict | None:
    path = tk.workspace_path(plan.workspace_id) + "/job"
    if plan.job_id:
        return tk.request(path + "/" + plan.job_id)["data"]
    data = tk.request(path)["data"]
    if not isinstance(data, list):
        raise HTTPException(502, "원격 Run 목록 형식이 올바르지 않습니다.")
    matches = [item for item in data if isinstance(item, dict)
               and (item.get("attributes") or {}).get("comments") == marker(plan.id)]
    if len(matches) > 1:
        raise HTTPException(409, "같은 요청의 원격 Run이 여러 개입니다. Terrakube에서 확인하세요.")
    return matches[0] if matches else None


def result_for(plan, job: dict) -> tuple[str, dict]:
    attrs = job.get("attributes") or {}
    job_id = str(job.get("id", ""))
    if (not job_id.isdigit() or (plan.job_id and plan.job_id != job_id)
            or attrs.get("comments") != marker(plan.id)
            or attrs.get("overrideBranch") != plan.workspace_snapshot.get("execution_ref", plan.commit_sha)
            or not valid_tcl(attrs.get("tcl"))):
        raise HTTPException(409, "원격 Run의 요청·commit·Plan 템플릿이 일치하지 않습니다.")
    observed_commit = attrs.get("commitId")
    if observed_commit and observed_commit != plan.commit_sha:
        raise HTTPException(409, "실행된 Git commit이 요청한 commit과 다릅니다.")
    remote_status = attrs.get("status", "unknown")
    if remote_status not in {"completed", "failed", "cancelled", "pending", "queue", "running", "waitingApproval"}:
        remote_status = "unknown"
    status = {"completed": "success", "failed": "failed", "cancelled": "cancelled",
              "pending": "pending", "queue": "pending", "running": "running"}.get(remote_status, "unknown")
    if status == "success" and not observed_commit:
        status = "unknown"
    return status, {"job_id": job_id, "remote_status": remote_status, "commit_sha": observed_commit,
                    "has_changes": attrs.get("planChanges") if status == "success" and type(attrs.get("planChanges")) is bool else None,
                    "url": f"{tk.workspace_link(plan.workspace_id)}/runs/{job_id}" if settings.terrakube_ui_url else None}
