"""Provider-neutral target endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.aws_connection import AwsConnection
from eolgae.models.environment import Environment
from eolgae.models.target import Target
from eolgae.models.user import User
from eolgae.routers.environments import slugify
from eolgae.schemas.target import (
    KubernetesReadOnlyManifestResponse,
    TargetCreate,
    TargetResponse,
    TargetUpdate,
    TargetVerifyResponse,
)
from eolgae.services.kubernetes_onboarding import build_read_only_manifest
from eolgae.services.target_verification import (
    verify_aws_target,
    verify_kubernetes_target,
)

router = APIRouter(prefix="/targets", tags=["targets"])


def _err(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _unique_target_slug(
    db: Session,
    *,
    owner_id: UUID,
    value: str,
    exclude_target_id: UUID | None = None,
) -> str:
    base = slugify(value)
    slug = base
    counter = 2
    while True:
        query = select(Target.id).where(Target.owner_id == owner_id, Target.slug == slug)
        if exclude_target_id is not None:
            query = query.where(Target.id != exclude_target_id)
        if db.scalar(query) is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def _owned_target(db: Session, target_id: UUID, user: User) -> Target:
    target = db.get(Target, target_id)
    if target is None or target.owner_id != user.id or target.deleted_at is not None:
        raise _err(status.HTTP_404_NOT_FOUND, "target_not_found", "target not found")
    return target


def _validate_environment(
    db: Session,
    environment_id: UUID | None,
    user: User,
) -> None:
    if environment_id is None:
        return
    environment = db.get(Environment, environment_id)
    if (
        environment is None
        or environment.owner_id != user.id
        or environment.deleted_at is not None
    ):
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "environment_not_available",
            "environment is not available",
        )


def _validate_aws_connection(
    db: Session,
    aws_connection_id: UUID | None,
    user: User,
) -> None:
    if aws_connection_id is None:
        return
    connection = db.get(AwsConnection, aws_connection_id)
    if connection is None or connection.owner_id != user.id:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "aws_connection_not_available",
            "aws connection is not available",
        )


@router.get("", response_model=list[TargetResponse])
def list_targets(
    kind: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Target]:
    query = select(Target).where(Target.owner_id == user.id, Target.deleted_at.is_(None))
    if kind:
        query = query.where(Target.kind == kind)
    return list(
        db.scalars(
            query.order_by(Target.updated_at.desc(), Target.created_at.desc())
        ).all()
    )


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(
    payload: TargetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Target:
    _validate_environment(db, payload.environment_id, user)
    _validate_aws_connection(db, payload.aws_connection_id, user)
    target = Target(
        owner_id=user.id,
        name=payload.name,
        slug=_unique_target_slug(
            db,
            owner_id=user.id,
            value=payload.slug or payload.name,
        ),
        kind=payload.kind,
        provider=payload.provider or (
            "aws" if payload.kind == "aws_account" else "kubernetes"
        ),
        status="pending" if payload.kind == "kubernetes_cluster" else "draft",
        environment_id=payload.environment_id,
        aws_connection_id=payload.aws_connection_id,
        endpoint=payload.endpoint,
        config=payload.config,
        secret_ref=payload.secret_ref,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.get(
    "/kubernetes/read-only-manifest",
    response_model=KubernetesReadOnlyManifestResponse,
)
def get_kubernetes_read_only_manifest(
    namespace: str = "eolgae-system",
    service_account_name: str = "eolgae-reader",
    cluster_role_name: str = "eolgae-readonly",
    cluster_role_binding_name: str = "eolgae-reader",
    user: User = Depends(get_current_user),
) -> KubernetesReadOnlyManifestResponse:
    del user
    manifest = build_read_only_manifest(
        namespace=namespace,
        service_account_name=service_account_name,
        cluster_role_name=cluster_role_name,
        cluster_role_binding_name=cluster_role_binding_name,
    )
    return KubernetesReadOnlyManifestResponse(**manifest.__dict__)


@router.get("/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Target:
    return _owned_target(db, target_id, user)


@router.patch("/{target_id}", response_model=TargetResponse)
def update_target(
    target_id: UUID,
    payload: TargetUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Target:
    target = _owned_target(db, target_id, user)
    _validate_environment(db, payload.environment_id, user)
    if payload.name is not None:
        target.name = payload.name
    if payload.slug is not None:
        target.slug = _unique_target_slug(
            db,
            owner_id=user.id,
            value=payload.slug,
            exclude_target_id=target.id,
        )
    if payload.environment_id is not None:
        target.environment_id = payload.environment_id
    if payload.endpoint is not None:
        target.endpoint = payload.endpoint
    if payload.config is not None:
        target.config = payload.config
    if payload.secret_ref is not None:
        target.secret_ref = payload.secret_ref
    if payload.status is not None:
        target.status = payload.status
    if payload.archived is not None:
        target.archived_at = datetime.now(timezone.utc) if payload.archived else None
        target.status = "archived" if payload.archived else "draft"
    db.commit()
    db.refresh(target)
    return target


@router.post("/{target_id}/verify", response_model=TargetVerifyResponse)
def verify_target(
    target_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetVerifyResponse:
    target = _owned_target(db, target_id, user)

    if target.kind == "aws_account":
        connection = (
            db.get(AwsConnection, target.aws_connection_id)
            if target.aws_connection_id
            else None
        )
        if connection is not None and connection.owner_id != user.id:
            connection = None
        verification = verify_aws_target(connection)
    elif target.kind == "kubernetes_cluster":
        verification = verify_kubernetes_target(target)
    else:
        raise _err(status.HTTP_400_BAD_REQUEST, "unsupported_target_kind", "unsupported target kind")

    target.status = verification.status
    target.last_error = verification.last_error
    target.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(target)
    return TargetVerifyResponse(
        ok=verification.ok,
        mode=verification.mode,
        status=target.status,
        message=verification.message,
        checks=verification.checks,
        last_verified_at=target.last_verified_at,
    )


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    target = _owned_target(db, target_id, user)
    target.deleted_at = datetime.now(timezone.utc)
    db.commit()
