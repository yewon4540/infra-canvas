"""Project Group endpoints — 업무/프로젝트 그룹 CRUD + 운영 연결.

CANVAS-GROUP-SPEC.md §3. ownership / group 매핑은 `canvases.owner_id` /
`canvases.group_id` 컬럼 기반 ([[0009_consolidate_canvas_columns]] 흡수 후).
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.aws_connection import AwsConnection
from eolgae.models.canvas import Canvas
from eolgae.models.canvas_group import CanvasGroup
from eolgae.models.environment import Environment
from eolgae.models.group_aws_connection import GroupAwsConnection
from eolgae.models.user import User
from eolgae.routers.environments import ensure_default_environments, slugify
from eolgae.schemas.group import (
    CanvasGroupCreate,
    CanvasGroupResponse,
    CanvasGroupUpdate,
    CanvasInGroupResponse,
    CanvasOwnerResponse,
    EnvironmentSummary,
    GroupAwsConnectionAttach,
    GroupAwsConnectionSummary,
)

router = APIRouter(prefix="/groups", tags=["groups"])


def _err(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _get_owned_group(db: Session, group_id: UUID, user: User, *, allow_trashed: bool = False) -> CanvasGroup:
    group = db.get(CanvasGroup, group_id)
    if group is None or group.owner_id != user.id:
        raise _err(status.HTTP_404_NOT_FOUND, "group_not_found", "group not found")
    if not allow_trashed and group.deleted_at is not None:
        raise _err(status.HTTP_404_NOT_FOUND, "group_not_found", "group not found")
    return group


def _owned_environment_or_none(
    db: Session,
    environment_id: UUID | None,
    user: User,
) -> Environment | None:
    if environment_id is None:
        return None
    environment = db.get(Environment, environment_id)
    if environment is None or environment.owner_id != user.id:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "environment_not_available",
            "environment is not available",
        )
    return environment


def _owned_connection(db: Session, connection_id: UUID, user: User) -> AwsConnection:
    connection = db.get(AwsConnection, connection_id)
    if connection is None or connection.owner_id != user.id:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "aws_connection_not_available",
            "aws connection is not available",
        )
    return connection


def _connection_summary(
    connection: AwsConnection,
    *,
    is_default: bool = False,
) -> GroupAwsConnectionSummary:
    return GroupAwsConnectionSummary(
        id=connection.id,
        name=connection.name,
        account_id=connection.account_id,
        default_region=connection.default_region,
        binding_status=connection.binding_status,
        permission_mode=connection.permission_mode,
        is_default=is_default,
    )


def _environment_summary(environment: Environment | None) -> EnvironmentSummary | None:
    if environment is None:
        return None
    return EnvironmentSummary(
        id=environment.id,
        name=environment.name,
        slug=environment.slug,
        risk_level=environment.risk_level,
    )


def _unique_group_slug(
    db: Session,
    *,
    owner_id: UUID,
    value: str,
    exclude_group_id: UUID | None = None,
) -> str:
    base = slugify(value)
    slug = base
    counter = 2
    while True:
        query = select(CanvasGroup.id).where(
            CanvasGroup.owner_id == owner_id,
            CanvasGroup.slug == slug,
        )
        if exclude_group_id is not None:
            query = query.where(CanvasGroup.id != exclude_group_id)
        if db.scalar(query) is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def _group_response(db: Session, group: CanvasGroup) -> CanvasGroupResponse:
    rows = db.execute(
        select(GroupAwsConnection, AwsConnection)
        .join(AwsConnection, GroupAwsConnection.aws_connection_id == AwsConnection.id)
        .where(GroupAwsConnection.group_id == group.id)
        .order_by(GroupAwsConnection.is_default.desc(), AwsConnection.updated_at.desc())
    ).all()
    connections = [
        _connection_summary(connection, is_default=link.is_default)
        for link, connection in rows
    ]
    canvas_stats = db.execute(
        select(func.count(Canvas.id), func.max(Canvas.updated_at)).where(
            Canvas.group_id == group.id,
            Canvas.deleted_at.is_(None),
        )
    ).one()
    default_environment = (
        db.get(Environment, group.default_environment_id)
        if group.default_environment_id
        else None
    )
    return CanvasGroupResponse(
        id=group.id,
        owner_id=group.owner_id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        color=group.color,
        status=group.status,
        default_environment_id=group.default_environment_id,
        default_environment=_environment_summary(default_environment),
        default_aws_connection=next(
            (connection for connection in connections if connection.is_default),
            None,
        ),
        connected_aws_connections=connections,
        canvas_count=canvas_stats[0] or 0,
        last_activity_at=canvas_stats[1],
        sort_order=group.sort_order,
        created_at=group.created_at,
        updated_at=group.updated_at,
        deleted_at=group.deleted_at,
    )


# ===== Group CRUD =====


@router.get("", response_model=list[CanvasGroupResponse])
def list_groups(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CanvasGroup]:
    groups = db.scalars(
        select(CanvasGroup)
        .where(CanvasGroup.owner_id == user.id, CanvasGroup.deleted_at.is_(None))
        .order_by(CanvasGroup.sort_order.asc(), CanvasGroup.created_at.asc())
    ).all()
    return [_group_response(db, group) for group in groups]


@router.get("/trash", response_model=list[CanvasGroupResponse])
def list_groups_trash(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CanvasGroup]:
    groups = db.scalars(
        select(CanvasGroup)
        .where(CanvasGroup.owner_id == user.id, CanvasGroup.deleted_at.is_not(None))
        .order_by(CanvasGroup.deleted_at.desc())
    ).all()
    return [_group_response(db, group) for group in groups]


@router.post("", response_model=CanvasGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: CanvasGroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CanvasGroup:
    ensure_default_environments(db, user)
    _owned_environment_or_none(db, payload.default_environment_id, user)
    group = CanvasGroup(
        owner_id=user.id,
        name=payload.name,
        slug=_unique_group_slug(
            db,
            owner_id=user.id,
            value=payload.slug or payload.name,
        ),
        description=payload.description,
        color=payload.color,
        default_environment_id=payload.default_environment_id,
        sort_order=payload.sort_order,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_response(db, group)


@router.get("/{group_id}", response_model=CanvasGroupResponse)
def get_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CanvasGroupResponse:
    return _group_response(db, _get_owned_group(db, group_id, user))


@router.patch("/{group_id}", response_model=CanvasGroupResponse)
def update_group(
    group_id: UUID,
    payload: CanvasGroupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CanvasGroupResponse:
    group = _get_owned_group(db, group_id, user)
    if payload.name is not None:
        group.name = payload.name
    if payload.slug is not None:
        group.slug = _unique_group_slug(
            db,
            owner_id=user.id,
            value=payload.slug,
            exclude_group_id=group.id,
        )
    if payload.description is not None:
        group.description = payload.description
    if payload.color is not None:
        group.color = payload.color
    if payload.status is not None:
        group.status = payload.status
    if payload.default_environment_id is not None:
        _owned_environment_or_none(db, payload.default_environment_id, user)
        group.default_environment_id = payload.default_environment_id
    if payload.sort_order is not None:
        group.sort_order = payload.sort_order
    db.commit()
    db.refresh(group)
    return _group_response(db, group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    group = _get_owned_group(db, group_id, user)
    group.deleted_at = datetime.now(tz=timezone.utc)
    db.commit()


@router.post("/{group_id}/restore", response_model=CanvasGroupResponse)
def restore_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CanvasGroupResponse:
    group = _get_owned_group(db, group_id, user, allow_trashed=True)
    if group.deleted_at is None:
        raise _err(status.HTTP_409_CONFLICT, "not_trashed", "group is not in trash")
    group.deleted_at = None
    db.commit()
    db.refresh(group)
    return _group_response(db, group)


# ===== Group ↔ AWS Connection =====


@router.get(
    "/{group_id}/aws-connections",
    response_model=list[GroupAwsConnectionSummary],
)
def list_group_aws_connections(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupAwsConnectionSummary]:
    _get_owned_group(db, group_id, user)
    rows = db.execute(
        select(GroupAwsConnection, AwsConnection)
        .join(AwsConnection, GroupAwsConnection.aws_connection_id == AwsConnection.id)
        .where(GroupAwsConnection.group_id == group_id)
        .order_by(GroupAwsConnection.is_default.desc(), AwsConnection.updated_at.desc())
    ).all()
    return [
        _connection_summary(connection, is_default=link.is_default)
        for link, connection in rows
    ]


@router.post(
    "/{group_id}/aws-connections",
    response_model=list[GroupAwsConnectionSummary],
    status_code=status.HTTP_201_CREATED,
)
def attach_group_aws_connection(
    group_id: UUID,
    payload: GroupAwsConnectionAttach,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupAwsConnectionSummary]:
    _get_owned_group(db, group_id, user)
    _owned_connection(db, payload.aws_connection_id, user)
    if payload.is_default:
        db.query(GroupAwsConnection).filter(
            GroupAwsConnection.group_id == group_id
        ).update({"is_default": False})
    link = db.get(GroupAwsConnection, (group_id, payload.aws_connection_id))
    if link is None:
        link = GroupAwsConnection(
            group_id=group_id,
            aws_connection_id=payload.aws_connection_id,
            is_default=payload.is_default,
        )
        db.add(link)
    else:
        link.is_default = payload.is_default or link.is_default
    db.commit()
    return list_group_aws_connections(group_id, user, db)


@router.put(
    "/{group_id}/aws-connections/{connection_id}/default",
    response_model=list[GroupAwsConnectionSummary],
)
def set_group_default_aws_connection(
    group_id: UUID,
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupAwsConnectionSummary]:
    _get_owned_group(db, group_id, user)
    _owned_connection(db, connection_id, user)
    link = db.get(GroupAwsConnection, (group_id, connection_id))
    if link is None:
        link = GroupAwsConnection(
            group_id=group_id,
            aws_connection_id=connection_id,
            is_default=True,
        )
        db.add(link)
    db.query(GroupAwsConnection).filter(
        GroupAwsConnection.group_id == group_id
    ).update({"is_default": False})
    link.is_default = True
    db.commit()
    return list_group_aws_connections(group_id, user, db)


@router.delete(
    "/{group_id}/aws-connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_group_aws_connection(
    group_id: UUID,
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_group(db, group_id, user)
    link = db.get(GroupAwsConnection, (group_id, connection_id))
    if link is None:
        raise _err(status.HTTP_404_NOT_FOUND, "link_not_found", "link not found")
    db.delete(link)
    db.commit()


@router.delete("/{group_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    group = _get_owned_group(db, group_id, user, allow_trashed=True)
    if group.deleted_at is None:
        raise _err(
            status.HTTP_409_CONFLICT,
            "must_trash_first",
            "soft-delete before permanent delete",
        )
    db.delete(group)
    db.commit()


# ===== Group ↔ Canvas =====


@router.get("/{group_id}/canvases", response_model=list[CanvasInGroupResponse])
def list_group_canvases(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Canvas]:
    _get_owned_group(db, group_id, user)
    canvases = db.scalars(
        select(Canvas)
        .where(
            Canvas.group_id == group_id,
            Canvas.deleted_at.is_(None),
        )
        .order_by(Canvas.updated_at.desc())
    ).all()
    return list(canvases)


def _ensure_canvas_owner(canvas: Canvas, user: User) -> None:
    """canvas owner = user 검증. 미 claim (owner_id NULL) 이면 자동 claim."""
    if canvas.owner_id is None:
        canvas.owner_id = user.id
        return
    if canvas.owner_id != user.id:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "not_canvas_owner",
            "canvas belongs to another user",
        )


@router.post(
    "/{group_id}/canvases/{canvas_id}",
    response_model=CanvasInGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_canvas_to_group(
    group_id: UUID,
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    group = _get_owned_group(db, group_id, user)
    canvas = db.get(Canvas, canvas_id)
    if canvas is None or canvas.deleted_at is not None:
        raise _err(status.HTTP_404_NOT_FOUND, "canvas_not_found", "canvas not found")

    _ensure_canvas_owner(canvas, user)

    # 1캔버스 = 1그룹 — group_id 교체로 충분 (컬럼 기반)
    canvas.group_id = group.id
    if canvas.environment_id is None:
        canvas.environment_id = group.default_environment_id
    db.commit()
    db.refresh(canvas)
    return canvas


@router.delete(
    "/{group_id}/canvases/{canvas_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_canvas_from_group(
    group_id: UUID,
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_group(db, group_id, user)
    canvas = db.get(Canvas, canvas_id)
    if canvas is None or canvas.group_id != group_id:
        raise _err(
            status.HTTP_404_NOT_FOUND,
            "membership_not_found",
            "canvas is not in this group",
        )
    canvas.group_id = None
    db.commit()


# ===== Canvas ownership (CANVAS-GROUP-SPEC §3.3) =====
# 별도 prefix 라우터 — /canvases/... 는 본 router 의 prefix(/groups) 와 다름.
ownership_router = APIRouter(prefix="/canvases", tags=["ownership"])


@ownership_router.post(
    "/{canvas_id}/claim", response_model=CanvasOwnerResponse, status_code=status.HTTP_201_CREATED
)
def claim_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    canvas = db.get(Canvas, canvas_id)
    if canvas is None:
        raise _err(status.HTTP_404_NOT_FOUND, "canvas_not_found", "canvas not found")
    if canvas.owner_id is not None:
        if canvas.owner_id != user.id:
            raise _err(
                status.HTTP_403_FORBIDDEN, "already_claimed", "canvas claimed by another user"
            )
        return {"canvas_id": canvas.id, "owner_id": canvas.owner_id}
    canvas.owner_id = user.id
    db.commit()
    db.refresh(canvas)
    return {"canvas_id": canvas.id, "owner_id": canvas.owner_id}


@ownership_router.get("/{canvas_id}/owner", response_model=CanvasOwnerResponse)
def get_canvas_owner(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    canvas = db.get(Canvas, canvas_id)
    if canvas is None:
        raise _err(status.HTTP_404_NOT_FOUND, "canvas_not_found", "canvas not found")
    if canvas.owner_id is None:
        raise _err(status.HTTP_404_NOT_FOUND, "owner_not_found", "canvas not claimed")
    return {"canvas_id": canvas.id, "owner_id": canvas.owner_id}
