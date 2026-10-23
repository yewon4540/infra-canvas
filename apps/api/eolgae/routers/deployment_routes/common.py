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

REPEAT_APPLY_DETAIL = (
    "이미 이 Plan으로 Apply가 생성되었습니다. 새 Plan을 실행한 뒤 다시 승인하세요."
)
REPEAT_DESTROY_DETAIL = (
    "이미 이 Destroy Plan으로 실행이 생성되었습니다. 새 Destroy Plan을 실행한 뒤 다시 승인하세요."
)



def _owned_canvas(db: Session, canvas_id: UUID, user: User) -> Canvas:
    canvas = db.get(Canvas, canvas_id, with_for_update=True)
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
