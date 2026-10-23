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
    "/{canvas_id}/deployments/plan",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_plan_deployment(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    """Snapshot the canvas and enqueue a cross-account Plan job."""
    canvas = _owned_canvas(db, canvas_id, user)
    require_direct_execution(canvas)
    aws_account = effective_aws_account(db, canvas)
    if aws_account.get("binding_status") != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan 전에 AWS 계정 연결 검증이 필요",
        )
    if not aws_account.get("role_arn") or not aws_account.get("external_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 과 External ID 가 필요",
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
            detail="이미 진행 중인 Plan이 있음",
        )

    version_number = (
        db.scalar(
            select(func.max(CanvasVersion.version_number)).where(
                CanvasVersion.canvas_id == canvas.id
            )
        )
        or 0
    ) + 1
    version = CanvasVersion(
        canvas_id=canvas.id,
        version_number=version_number,
        graph=canvas.graph,
        commit_message="before async plan",
        author_id=user.id,
    )
    db.add(version)
    db.flush()

    deployment = Deployment(
        canvas_id=canvas.id,
        canvas_version_id=version.id,
        status="queued",
        mode="plan",
        aws_account_snapshot=aws_account,
        initiated_by=user.id,
        progress_events=[
            {
                "step": "queue",
                "label": "Plan 큐 등록",
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
                "mode": "plan",
                "canvas_version_id": str(version.id),
            },
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 진행 중인 Plan이 있음",
        ) from exc

    try:
        run_plan.send(str(deployment.id))
    except Exception as exc:
        deployment.status = "failed"
        deployment.error_message = "Plan 큐 등록 실패"
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


@router.post(
    "/{canvas_id}/deployments/destroy-plan",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_destroy_plan_deployment(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    """Snapshot the canvas and enqueue a remote-state destroy Plan job."""
    canvas = _owned_canvas(db, canvas_id, user)
    require_direct_execution(canvas)
    if canvas.state not in ("applied", "running", "deploy"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apply 완료 상태의 캔버스만 Destroy Plan을 실행할 수 있음",
        )
    aws_account = effective_aws_account(db, canvas)
    if aws_account.get("binding_status") != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Destroy 전에 AWS 계정 연결 검증이 필요",
        )
    if not aws_account.get("role_arn") or not aws_account.get("external_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 과 External ID 가 필요",
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
            detail="이미 진행 중인 Plan, Apply 또는 Destroy가 있음",
        )

    version_number = (
        db.scalar(
            select(func.max(CanvasVersion.version_number)).where(
                CanvasVersion.canvas_id == canvas.id
            )
        )
        or 0
    ) + 1
    version = CanvasVersion(
        canvas_id=canvas.id,
        version_number=version_number,
        graph=canvas.graph,
        commit_message="before destroy plan",
        author_id=user.id,
    )
    db.add(version)
    db.flush()

    deployment = Deployment(
        canvas_id=canvas.id,
        canvas_version_id=version.id,
        status="queued",
        mode="destroy",
        aws_account_snapshot=aws_account,
        initiated_by=user.id,
        progress_events=[
            {
                "step": "queue",
                "label": "Destroy Plan 큐 등록",
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
                "mode": "destroy",
                "canvas_version_id": str(version.id),
            },
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 진행 중인 Plan, Apply 또는 Destroy가 있음",
        ) from exc

    try:
        run_plan.send(str(deployment.id))
    except Exception as exc:
        deployment.status = "failed"
        deployment.error_message = "Destroy Plan 큐 등록 실패"
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
