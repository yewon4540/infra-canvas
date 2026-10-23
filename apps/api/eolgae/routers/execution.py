"""Installed capabilities and immutable external execution bindings."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.config import settings
from eolgae.db import get_db
from eolgae.integrations import terrakube
from eolgae.integrations.terrakube_plan import plan_allowed
from eolgae.models.canvas import Canvas
from eolgae.models.deployment import AuditLog, Deployment
from eolgae.models.user import User
from eolgae.routers.deployment_routes.common import _owned_canvas

router = APIRouter(tags=["execution"])


@router.get("/execution/capabilities")
def capabilities(user: User = Depends(get_current_user)) -> dict:
    return {"direct_execution": settings.direct_execution_enabled,
            "terrakube": terrakube.authorized(user.id),
            "terrakube_configured": terrakube.authorized(user.id) and terrakube.configured(),
            "terrakube_operations": (["read", "plan"] if plan_allowed(user.id) else ["read"]) if terrakube.authorized(user.id) else [],
            "legacy_sync_plan": False}


def binding_response(canvas: Canvas) -> dict:
    backend = canvas.execution_backend
    return {"backend": backend, "workspace_id": canvas.terrakube_workspace_id,
            "direct_execution": settings.direct_execution_enabled and backend == "eolgae_direct"}


@router.get("/canvas/{canvas_id}/execution")
def get_binding(canvas_id: UUID, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    return binding_response(_owned_canvas(db, canvas_id, user))


class BindTerrakube(BaseModel):
    workspace_id: UUID


@router.put("/canvas/{canvas_id}/execution/terrakube")
def bind_terrakube(canvas_id: UUID, body: BindTerrakube,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    workspace_id = str(body.workspace_id)
    terrakube.require_access(user.id, workspace_id)
    canvas = _owned_canvas(db, canvas_id, user)
    if canvas.execution_backend == "terrakube":
        if canvas.terrakube_workspace_id == workspace_id:
            return binding_response(canvas)
        raise HTTPException(409, "기존 실행 연결은 변경할 수 없습니다.")
    if db.scalar(select(Deployment.id).where(Deployment.canvas_id == canvas.id).limit(1)):
        raise HTTPException(409, "실행 이력이 있는 Canvas는 별도 State 이전 검토가 필요합니다.")
    if canvas.state not in {"design", "draft"}:
        raise HTTPException(409, "설계 상태의 Canvas만 연결할 수 있습니다.")
    terrakube.get_workspace(workspace_id)
    canvas.execution_backend = "terrakube"
    canvas.terrakube_workspace_id = workspace_id
    db.add(AuditLog(actor_id=user.id, action="execution.bind", entity_type="canvas",
                    entity_id=canvas.id, after={"backend": "terrakube", "workspace_id": workspace_id}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이미 연결된 Workspace입니다.") from None
    return binding_response(canvas)


@router.get("/integrations/terrakube/workspaces")
def workspaces(user: User = Depends(get_current_user)) -> dict:
    terrakube.require_access(user.id)
    items, errors = [], []
    for workspace_id in sorted(terrakube.identifiers(settings.terrakube_workspace_ids)):
        try:
            items.append(terrakube.get_workspace(workspace_id))
        except HTTPException as exc:
            errors.append({"workspace_id": workspace_id, "status": exc.status_code, "message": exc.detail})
    if not items and not errors:
        raise HTTPException(503, "조회할 Workspace 설정이 필요합니다.")
    return {"items": items, "errors": errors}


@router.get("/integrations/terrakube/workspaces/{workspace_id}/jobs")
def jobs(workspace_id: UUID, user: User = Depends(get_current_user)) -> dict:
    terrakube.require_access(user.id, str(workspace_id))
    return terrakube.get_jobs(str(workspace_id))


@router.get("/integrations/terrakube/workspaces/{workspace_id}/canvases")
def bound_canvases(workspace_id: UUID, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    terrakube.require_access(user.id, str(workspace_id))
    rows = db.scalars(select(Canvas).where(Canvas.owner_id == user.id, Canvas.deleted_at.is_(None),
        Canvas.execution_backend == "terrakube", Canvas.terrakube_workspace_id == str(workspace_id))).all()
    return {"items": [{"id": str(canvas.id), "name": canvas.name} for canvas in rows]}
