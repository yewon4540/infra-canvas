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

@router.get("/deployments/summary")
def deployment_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Dashboard summary for the current user's deployment operations."""
    return deployment_summary_for_user(db, user.id)


@router.get("/{canvas_id}/deployments/history")
def canvas_deployment_history(
    canvas_id: UUID,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Canvas detail run history for Plan / Apply / Destroy operations."""
    canvas = _owned_canvas(db, canvas_id, user)
    return deployment_history_for_canvas(
        db,
        canvas_id=canvas.id,
        limit=limit,
    )


@router.get(
    "/{canvas_id}/deployments/{deployment_id}",
    response_model=DeploymentResponse,
)
def get_deployment(
    canvas_id: UUID,
    deployment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    _owned_canvas(db, canvas_id, user)
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
    return deployment
