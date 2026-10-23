"""Owner-scoped Kubernetes read endpoints, independent of Canvas/execution."""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.user import User
from eolgae.routers.targets import _owned_target
from eolgae.integrations.kubernetes.access import scope_for
from eolgae.services.resource_observation import observe

router = APIRouter(prefix="/targets", tags=["resources"])


@router.get("/{target_id}/resource-scope")
def resource_scope(target_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return scope_for(_owned_target(db, target_id, user))


@router.get("/{target_id}/resources")
def list_resources(target_id: UUID, namespace: str | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return observe(_owned_target(db, target_id, user), namespace)
