"""Environment settings endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.environment import Environment
from eolgae.models.user import User
from eolgae.schemas.environment import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
)

router = APIRouter(prefix="/environments", tags=["environments"])

DEFAULT_ENVIRONMENTS = [
    ("Development", "dev", "개발/실험 환경", "low", 10),
    ("Staging", "stg", "운영 반영 전 검증 환경", "medium", 20),
    ("Production", "prd", "운영 환경", "high", 30),
    ("Shared", "shared", "공유 인프라 환경", "medium", 40),
    ("Sandbox", "sandbox", "임시 테스트 환경", "low", 50),
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or f"env-{uuid4().hex[:8]}"


def _err(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def ensure_default_environments(db: Session, user: User) -> None:
    existing = set(
        db.scalars(select(Environment.slug).where(Environment.owner_id == user.id)).all()
    )
    created = False
    for name, slug, description, risk_level, sort_order in DEFAULT_ENVIRONMENTS:
        if slug in existing:
            continue
        db.add(
            Environment(
                owner_id=user.id,
                name=name,
                slug=slug,
                description=description,
                risk_level=risk_level,
                sort_order=sort_order,
            )
        )
        created = True
    if created:
        db.commit()


def _owned_environment(db: Session, environment_id: UUID, user: User) -> Environment:
    environment = db.get(Environment, environment_id)
    if environment is None or environment.owner_id != user.id:
        raise _err(
            status.HTTP_404_NOT_FOUND,
            "environment_not_found",
            "environment not found",
        )
    if environment.deleted_at is not None:
        raise _err(
            status.HTTP_404_NOT_FOUND,
            "environment_not_found",
            "environment not found",
        )
    return environment


@router.get("", response_model=list[EnvironmentResponse])
def list_environments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Environment]:
    ensure_default_environments(db, user)
    return list(
        db.scalars(
            select(Environment)
            .where(Environment.owner_id == user.id, Environment.deleted_at.is_(None))
            .order_by(Environment.sort_order.asc(), Environment.created_at.asc())
        ).all()
    )


@router.post("", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED)
def create_environment(
    payload: EnvironmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Environment:
    environment = Environment(
        owner_id=user.id,
        name=payload.name,
        slug=slugify(payload.slug or payload.name),
        description=payload.description,
        risk_level=payload.risk_level,
        sort_order=payload.sort_order,
    )
    db.add(environment)
    db.commit()
    db.refresh(environment)
    return environment


@router.patch("/{environment_id}", response_model=EnvironmentResponse)
def update_environment(
    environment_id: UUID,
    payload: EnvironmentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Environment:
    environment = _owned_environment(db, environment_id, user)
    if payload.name is not None:
        environment.name = payload.name
    if payload.slug is not None:
        environment.slug = slugify(payload.slug)
    if payload.description is not None:
        environment.description = payload.description
    if payload.risk_level is not None:
        environment.risk_level = payload.risk_level
    if payload.sort_order is not None:
        environment.sort_order = payload.sort_order
    if payload.archived is not None:
        environment.archived_at = (
            datetime.now(timezone.utc) if payload.archived else None
        )
    db.commit()
    db.refresh(environment)
    return environment


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(
    environment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    environment = _owned_environment(db, environment_id, user)
    environment.deleted_at = datetime.now(timezone.utc)
    db.commit()
