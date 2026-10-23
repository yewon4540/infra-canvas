"""Owner-scoped remote Plan routes. No remote approve/apply/delete endpoint."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.integrations.terrakube_plan import plan_allowed
from eolgae.models.remote_plan import RemotePlan
from eolgae.models.user import User
from eolgae.routers.deployment_routes.common import _owned_canvas
from eolgae.services import remote_plans as service

router = APIRouter(prefix="/canvas", tags=["remote-plans"])


class RequestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    canvas_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/{canvas_id}/remote-plans")
def list_plans(canvas_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    canvas = _owned_canvas(db, canvas_id, user)
    service.require_binding(canvas, user.id)
    revision = service.canvas_revision(canvas)
    plans = db.scalars(select(RemotePlan).where(RemotePlan.canvas_id == canvas.id)
                       .order_by(RemotePlan.created_at.desc()).limit(20)).all()
    return {"canvas_revision": revision, "plan_enabled": plan_allowed(user.id),
            "items": [service.response(plan, revision) for plan in plans]}


@router.post("/{canvas_id}/remote-plans", status_code=202)
def submit_plan(canvas_id: UUID, body: RequestPlan, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    canvas = _owned_canvas(db, canvas_id, user)
    try:
        plan = service.create_plan(db, canvas, user.id, body)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "동시에 제출된 요청이 있습니다. 실행 이력을 다시 확인하세요.") from None
    return service.response(plan, service.canvas_revision(canvas))


@router.post("/{canvas_id}/remote-plans/{plan_id}/sync")
def sync_plan(canvas_id: UUID, plan_id: UUID, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    canvas = _owned_canvas(db, canvas_id, user)
    service.require_binding(canvas, user.id)
    plan = db.get(RemotePlan, plan_id, with_for_update=True)
    if not plan or plan.canvas_id != canvas.id or plan.workspace_id != canvas.terrakube_workspace_id:
        raise HTTPException(404, "원격 Plan 요청을 찾을 수 없습니다.")
    return service.response(service.reconcile(db, plan, user.id), service.canvas_revision(canvas))
