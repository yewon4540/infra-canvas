"""Read models for deployment dashboard and history views."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.models.canvas import Canvas
from eolgae.models.deployment import Deployment


ACTIVE_STATUSES = ("queued", "planning", "applying", "destroying")


def deployment_summary_for_user(db: Session, user_id: UUID) -> dict:
    deployments = db.scalars(
        select(Deployment)
        .join(Canvas, Deployment.canvas_id == Canvas.id)
        .where(Canvas.owner_id == user_id, Canvas.deleted_at.is_(None))
    ).all()
    return {
        "total": len(deployments),
        "approval_pending": sum(
            1 for deployment in deployments if deployment.status == "success"
        ),
        "failed": sum(
            1 for deployment in deployments if deployment.status == "failed"
        ),
        "active": sum(
            1 for deployment in deployments if deployment.status in ACTIVE_STATUSES
        ),
        "applied": sum(
            1 for deployment in deployments if deployment.status == "applied"
        ),
        "destroyed": sum(
            1 for deployment in deployments if deployment.status == "destroyed"
        ),
        "recent": [
            _deployment_summary_item(deployment)
            for deployment in sorted(
                deployments,
                key=_deployment_created_timestamp,
                reverse=True,
            )[:5]
        ],
    }


def deployment_history_for_canvas(
    db: Session,
    *,
    canvas_id: UUID,
    limit: int = 20,
) -> dict:
    deployments = db.scalars(
        select(Deployment)
        .where(Deployment.canvas_id == canvas_id)
        .order_by(Deployment.created_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return {
        "canvas_id": str(canvas_id),
        "total_returned": len(deployments),
        "items": [_deployment_summary_item(deployment) for deployment in deployments],
    }


def _deployment_created_timestamp(deployment: Deployment) -> float:
    created_at = getattr(deployment, "created_at", None)
    if not created_at:
        return 0
    return created_at.timestamp()


def _deployment_summary_item(deployment: Deployment) -> dict:
    created_at = getattr(deployment, "created_at", None)
    finished_at = getattr(deployment, "finished_at", None)
    return {
        "id": str(getattr(deployment, "id", "")),
        "canvas_id": str(getattr(deployment, "canvas_id", "")),
        "mode": getattr(deployment, "mode", "plan"),
        "status": deployment.status,
        "created_at": created_at.isoformat() if created_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
        "error_message": getattr(deployment, "error_message", None),
        "requires_approval": deployment.status == "success",
        "source_plan_deployment_id": (
            str(deployment.source_plan_deployment_id)
            if getattr(deployment, "source_plan_deployment_id", None)
            else None
        ),
    }
