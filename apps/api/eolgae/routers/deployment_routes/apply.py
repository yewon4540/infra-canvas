from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.canvas import Canvas
from eolgae.models.deployment import AuditLog, CanvasVersion, Deployment
from eolgae.models.user import User
from eolgae.schemas.deployment import DeploymentResponse
from eolgae.services.aws_connections import effective_aws_account
from eolgae.services.deployment_insights import (
    ACTIVE_STATUSES,
    deployment_history_for_canvas,
    deployment_summary_for_user,
)
from eolgae.execution.dispatch import run_apply, run_destroy, run_plan

from eolgae.execution.policy import require_direct_execution
from .common import (
    _owned_canvas, _existing_apply_for_source_plan, _existing_destroy_for_source_plan, _integrity_constraint_name, REPEAT_APPLY_DETAIL, REPEAT_DESTROY_DETAIL
)

router = APIRouter(prefix="/canvas", tags=["deployments"])

@router.post(
    "/{canvas_id}/deployments/{deployment_id}/apply",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_apply_deployment(
    canvas_id: UUID,
    deployment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    """Enqueue Apply for an explicitly approved immutable Plan."""
    canvas = _owned_canvas(db, canvas_id, user)
    require_direct_execution(canvas)
    source_plan = db.scalar(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.canvas_id == canvas_id,
        )
    )
    if source_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )
    if source_plan.mode != "plan" or source_plan.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="승인된 Plan만 Apply할 수 있음",
        )
    if not source_plan.plan_artifact or not source_plan.state_backend:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apply에 필요한 Plan artifact 또는 state backend가 없음",
        )
    if _existing_apply_for_source_plan(db, source_plan.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=REPEAT_APPLY_DETAIL,
        )

    active = db.scalar(
        select(Deployment.id).where(
            Deployment.canvas_id == canvas.id,
            Deployment.status.in_(ACTIVE_STATUSES),
        )
    )
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 진행 중인 Plan 또는 Apply가 있음",
        )

    deployment = Deployment(
        canvas_id=canvas.id,
        canvas_version_id=source_plan.canvas_version_id,
        status="queued",
        mode="apply",
        aws_account_snapshot=source_plan.aws_account_snapshot,
        plan_artifact=source_plan.plan_artifact,
        state_backend=source_plan.state_backend,
        source_plan_deployment_id=source_plan.id,
        initiated_by=user.id,
        approved_by=source_plan.approved_by,
        approved_at=source_plan.approved_at,
        progress_events=[
            {
                "step": "queue",
                "label": "Apply 큐 등록",
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    db.add(deployment)
    db.flush()
    db.add(
        AuditLog(
            actor_id=user.id,
            action="deployment.start",
            entity_type="deployment",
            entity_id=deployment.id,
            after={
                "status": "queued",
                "mode": "apply",
                "canvas_version_id": str(source_plan.canvas_version_id),
                "source_plan_deployment_id": str(source_plan.id),
            },
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = "이미 진행 중인 Plan 또는 Apply가 있음"
        if "uq_deployments_apply_source_plan" in _integrity_constraint_name(exc):
            detail = REPEAT_APPLY_DETAIL
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    try:
        run_apply.send(str(deployment.id))
    except Exception as exc:
        deployment.status = "failed"
        deployment.error_message = "Apply 큐 등록 실패"
        deployment.finished_at = datetime.now(timezone.utc)
        db.add(
            AuditLog(
                actor_id=None,
                action="deployment.complete",
                entity_type="deployment",
                entity_id=deployment.id,
                after={
                    "status": "failed",
                    "error_message": deployment.error_message,
                },
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=deployment.error_message,
        ) from exc

    db.refresh(deployment)
    return deployment
