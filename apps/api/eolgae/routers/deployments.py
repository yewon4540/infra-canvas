"""Asynchronous cross-account OpenTofu Plan endpoints."""
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
from eolgae.workers.plan import run_apply, run_destroy, run_plan

router = APIRouter(prefix="/canvas", tags=["deployments"])
REPEAT_APPLY_DETAIL = (
    "이미 이 Plan으로 Apply가 생성되었습니다. 새 Plan을 실행한 뒤 다시 승인하세요."
)
REPEAT_DESTROY_DETAIL = (
    "이미 이 Destroy Plan으로 실행이 생성되었습니다. 새 Destroy Plan을 실행한 뒤 다시 승인하세요."
)


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


def _owned_canvas(db: Session, canvas_id: UUID, user: User) -> Canvas:
    canvas = db.get(Canvas, canvas_id)
    if canvas is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canvas not found",
        )
    if canvas.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="다른 사용자의 캔버스",
        )
    if canvas.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="휴지통의 캔버스는 Plan을 실행할 수 없음",
        )
    return canvas


def _existing_apply_for_source_plan(db: Session, source_plan_id: UUID) -> UUID | None:
    return db.scalar(
        select(Deployment.id).where(
            Deployment.mode == "apply",
            Deployment.source_plan_deployment_id == source_plan_id,
        )
    )


def _existing_destroy_for_source_plan(db: Session, source_plan_id: UUID) -> UUID | None:
    return db.scalar(
        select(Deployment.id).where(
            Deployment.mode == "destroy",
            Deployment.source_plan_deployment_id == source_plan_id,
        )
    )


def _integrity_constraint_name(exc: IntegrityError) -> str:
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name:
        return str(constraint_name)
    return str(orig or exc)


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
        deployment.error_message = f"Plan 큐 등록 실패: {exc}"
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
        deployment.error_message = f"Destroy Plan 큐 등록 실패: {exc}"
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
        deployment.error_message = f"Apply 큐 등록 실패: {exc}"
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
    "/{canvas_id}/deployments/{deployment_id}/destroy",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_destroy_deployment(
    canvas_id: UUID,
    deployment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Deployment:
    """Enqueue Destroy for an explicitly approved immutable destroy Plan."""
    canvas = _owned_canvas(db, canvas_id, user)
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
    if source_plan.mode != "destroy" or source_plan.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="승인된 Destroy Plan만 실행할 수 있음",
        )
    if not source_plan.plan_artifact or not source_plan.state_backend:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Destroy에 필요한 Plan artifact 또는 state backend가 없음",
        )
    if _existing_destroy_for_source_plan(db, source_plan.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=REPEAT_DESTROY_DETAIL,
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

    deployment = Deployment(
        canvas_id=canvas.id,
        canvas_version_id=source_plan.canvas_version_id,
        status="queued",
        mode="destroy",
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
                "label": "Destroy 큐 등록",
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
                "canvas_version_id": str(source_plan.canvas_version_id),
                "source_plan_deployment_id": str(source_plan.id),
            },
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = "이미 진행 중인 Plan, Apply 또는 Destroy가 있음"
        if "uq_deployments_destroy_source_plan" in _integrity_constraint_name(exc):
            detail = REPEAT_DESTROY_DETAIL
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    try:
        run_destroy.send(str(deployment.id))
    except Exception as exc:
        deployment.status = "failed"
        deployment.error_message = f"Destroy 큐 등록 실패: {exc}"
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
