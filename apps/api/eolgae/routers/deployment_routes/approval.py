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
    "/{canvas_id}/deployments/{deployment_id}/approve",
    response_model=DeploymentResponse,
)
def approve_plan_deployment(
    canvas_id: UUID,
    deployment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    """Mark a successful Plan as explicitly approved for a future Apply."""
    canvas = _owned_canvas(db, canvas_id, user)
    require_direct_execution(canvas)
    deployment = db.scalar(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.canvas_id == canvas_id,
        )
    )
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )
    if deployment.mode not in ("plan", "destroy"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan 또는 Destroy Plan deployment만 승인할 수 있음",
        )
    if deployment.status == "approved":
        return deployment
    if deployment.status != "success" or not (deployment.plan_result or {}).get("ok"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="성공한 Plan만 승인할 수 있음",
        )
    if not deployment.plan_artifact or not deployment.state_backend:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan artifact와 state backend가 있는 Plan만 승인할 수 있음",
        )

    deployment.status = "approved"
    deployment.approved_by = user.id
    deployment.approved_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_id=user.id,
            action="deployment.approve",
            entity_type="deployment",
            entity_id=deployment.id,
            after={
                "status": "approved",
                "mode": deployment.mode,
                "canvas_version_id": str(deployment.canvas_version_id),
            },
        )
    )
    db.commit()
    db.refresh(deployment)
    return deployment
