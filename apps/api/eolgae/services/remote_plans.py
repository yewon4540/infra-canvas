"""Submission lifecycle, immutable identity and no-retry reconciliation."""
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eolgae.config import settings
from eolgae.integrations import terrakube as tk, terrakube_plan as remote
from eolgae.models.deployment import AuditLog, CanvasVersion
from eolgae.models.remote_plan import ACTIVE_REMOTE_PLANS, RemotePlan


def canvas_revision(canvas) -> str:
    value = {"graph": canvas.graph, "schema_version": canvas.schema_version, "kind": canvas.canvas_kind}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def require_binding(canvas, user_id, *, submit=False):
    if canvas.execution_backend != "terrakube" or not canvas.terrakube_workspace_id:
        raise HTTPException(409, "Terrakube에 연결한 Canvas만 원격 Plan을 사용할 수 있습니다.")
    tk.require_access(user_id, canvas.terrakube_workspace_id)
    if submit:
        remote.require_plan_access(user_id, canvas.terrakube_workspace_id)


def require_identity(plan):
    if (plan.api_url != tk._url(settings.terrakube_api_url)
            or plan.organization_id != tk._organization()):
        raise HTTPException(409, "제출 당시 Terrakube 서버·조직과 현재 설정이 다릅니다.")


def audit(db, plan, user_id, action):
    db.add(AuditLog(actor_id=user_id, action=action, entity_type="remote_plan", entity_id=plan.id,
                    after={"status": plan.status, "job_id": plan.job_id, "operation": "plan"}))


def create_plan(db: Session, canvas, user_id, body) -> RemotePlan:
    require_binding(canvas, user_id, submit=True)
    existing = db.scalar(select(RemotePlan).where(RemotePlan.canvas_id == canvas.id,
                                                 RemotePlan.idempotency_key == body.idempotency_key))
    if existing:
        if existing.commit_sha != body.commit_sha or existing.canvas_revision != body.canvas_revision:
            raise HTTPException(409, "이미 사용한 요청 키의 입력을 변경할 수 없습니다.")
        return existing
    if canvas_revision(canvas) != body.canvas_revision:
        raise HTTPException(409, "Canvas가 변경되었습니다. 최신 내용을 확인한 뒤 다시 요청하세요.")
    if db.scalar(select(RemotePlan.id).where(RemotePlan.canvas_id == canvas.id,
                                            RemotePlan.status.in_(ACTIVE_REMOTE_PLANS)).limit(1)):
        raise HTTPException(409, "진행 중이거나 결과가 불확실한 요청이 있습니다. 먼저 상태를 확인하세요.")
    template_id = remote.approved_template()
    workspace = tk.get_workspace(canvas.terrakube_workspace_id)
    branch = workspace.get("branch")
    if not branch or branch == "remote-content" or "," in branch:
        raise HTTPException(409, "단일 Git branch에 연결한 Workspace가 필요합니다.")
    workspace["execution_ref"] = branch
    number = (db.scalar(select(func.max(CanvasVersion.version_number)).where(CanvasVersion.canvas_id == canvas.id)) or 0) + 1
    version = CanvasVersion(id=uuid4(), canvas_id=canvas.id, version_number=number,
                            graph=canvas.graph, author_id=user_id, commit_message="Terrakube Plan reference snapshot")
    db.add(version)
    db.flush()
    plan = RemotePlan(id=uuid4(), canvas_id=canvas.id, canvas_version_id=version.id,
                      initiated_by=user_id, idempotency_key=body.idempotency_key,
                      canvas_revision=body.canvas_revision, commit_sha=body.commit_sha,
                      api_url=tk._url(settings.terrakube_api_url), organization_id=tk._organization(),
                      workspace_id=canvas.terrakube_workspace_id, template_id=template_id,
                      template_sha256=remote.PLAN_DIGEST, workspace_snapshot=workspace,
                      operation="plan", status="submitting")
    db.add(plan)
    audit(db, plan, user_id, "remote_plan.requested")
    # Commit intent BEFORE any network write. A crash here is uncertain, never replayed.
    db.commit()
    try:
        plan.job_id = remote.submit(plan)
        plan.status = "pending"
    except remote.SubmissionUncertain:
        plan.status = "unknown"
        plan.error_message = "제출 응답을 확인하지 못했습니다. 재전송 없이 기존 Run을 조회하세요."
    except HTTPException as exc:
        plan.status = "failed"
        plan.error_message = str(exc.detail)
    audit(db, plan, user_id, "remote_plan.submitted")
    db.commit()
    db.refresh(plan)
    return plan


def reconcile(db: Session, plan: RemotePlan, user_id) -> RemotePlan:
    require_identity(plan)
    try:
        job = remote.lookup(plan)
        if job is None:
            plan.status = "unknown"
            plan.error_message = "일치하는 Run을 아직 찾지 못했습니다. 자동 재전송하지 않습니다."
        else:
            status, result = remote.result_for(plan, job)
            plan.job_id = result["job_id"]
            plan.status, plan.result, plan.error_message = status, result, None
            if status == "unknown":
                plan.error_message = "원격 실행 상태 또는 commit을 확정하지 못했습니다. Terrakube에서 확인하세요."
    except HTTPException as exc:
        # A transient read error must not free the active slot or hide a known result.
        plan.error_message = str(exc.detail)
        if exc.status_code == 409:
            plan.status = "unknown"
    audit(db, plan, user_id, "remote_plan.reconciled")
    db.commit()
    db.refresh(plan)
    return plan


def response(plan, revision):
    return {"id": str(plan.id), "canvas_version_id": str(plan.canvas_version_id),
            "canvas_revision": plan.canvas_revision, "stale": plan.canvas_revision != revision,
            "commit_sha": plan.commit_sha, "workspace_id": plan.workspace_id,
            "template_id": plan.template_id, "template_sha256": plan.template_sha256,
            "operation": plan.operation, "status": plan.status, "job_id": plan.job_id,
            "result": plan.result, "error_message": plan.error_message,
            "created_at": plan.created_at.isoformat(), "updated_at": plan.updated_at.isoformat()}
