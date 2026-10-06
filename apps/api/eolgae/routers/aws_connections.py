"""Reusable AWS connection management endpoints."""
from __future__ import annotations

import re
from urllib.parse import urlencode
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.config import settings
from eolgae.db import get_db
from eolgae.models.aws_connection import AwsConnection
from eolgae.models.canvas_group import CanvasGroup
from eolgae.models.group_aws_connection import GroupAwsConnection
from eolgae.models.user import User

router = APIRouter(prefix="/aws-connections", tags=["aws-connections"])

ROLE_ARN_RE = re.compile(
    r"^arn:aws:iam::(?P<account_id>\d{12}):role\/(?P<role_name>[\w+=,.@\-_/]+)$"
)


class AwsConnectionPrepareRequest(BaseModel):
    account_id: str
    region: str = "ap-northeast-2"


class AwsConnectionRoleRequest(BaseModel):
    role_arn: str


class AwsConnectionResponse(BaseModel):
    id: UUID
    name: str
    account_id: str
    default_region: str
    external_id: str
    role_arn: str | None = None
    binding_status: str
    permission_mode: str
    last_verify_error: str | None = None
    assumed_arn: str | None = None
    last_verified_at: str | None = None
    cloudformation_template: str | None = None
    cloudformation_quick_create_url: str | None = None
    connected_project_groups: list[dict] = Field(default_factory=list)


class AwsVerifyResponse(BaseModel):
    ok: bool
    status: str
    message: str
    assumed_arn: str | None = None


def _template_text() -> str:
    here = Path(__file__).resolve()
    for parent in here.parents:
        path = parent / "infrastructure" / "cross-account-role.yaml"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise RuntimeError("cross-account-role.yaml template not found")


def _quick_create_url(
    *,
    region: str,
    external_id: str,
    source_account_id: str,
    template_url: str,
) -> str | None:
    if not template_url or not source_account_id:
        return None
    params = urlencode(
        {
            "templateURL": template_url,
            "stackName": "IaCPlanRoleStack",
            "param_ExternalId": external_id,
            "param_SourceAccountId": source_account_id,
            "param_SourcePrincipalName": "IaC_user",
        }
    )
    return (
        f"https://console.aws.amazon.com/cloudformation/home?region={region}"
        f"#/stacks/quickcreate?{params}"
    )


def _to_response(
    connection: AwsConnection,
    *,
    db: Session | None = None,
    include_template: bool = False,
) -> AwsConnectionResponse:
    template = _template_text() if include_template else None
    quick_url = (
        _quick_create_url(
            region=connection.default_region,
            external_id=connection.external_id,
            source_account_id=settings.eolgae_aws_account_id or "",
            template_url=settings.cfn_template_url,
        )
        if include_template
        else None
    )
    groups = []
    if db is not None:
        rows = db.execute(
            select(CanvasGroup, GroupAwsConnection)
            .join(GroupAwsConnection, GroupAwsConnection.group_id == CanvasGroup.id)
            .where(
                GroupAwsConnection.aws_connection_id == connection.id,
                CanvasGroup.deleted_at.is_(None),
            )
            .order_by(CanvasGroup.name.asc())
        ).all()
        groups = [
            {
                "id": str(group.id),
                "name": group.name,
                "slug": group.slug,
                "is_default": link.is_default,
            }
            for group, link in rows
        ]
    return AwsConnectionResponse(
        id=connection.id,
        name=connection.name,
        account_id=connection.account_id,
        default_region=connection.default_region,
        external_id=connection.external_id,
        role_arn=connection.role_arn,
        binding_status=connection.binding_status,
        permission_mode=connection.permission_mode,
        last_verify_error=connection.last_verify_error,
        assumed_arn=connection.assumed_arn,
        last_verified_at=(
            connection.last_verified_at.isoformat()
            if connection.last_verified_at
            else None
        ),
        cloudformation_template=template,
        cloudformation_quick_create_url=quick_url,
        connected_project_groups=groups,
    )


def _owned_connection(
    db: Session,
    connection_id: UUID,
    user: User,
) -> AwsConnection:
    connection = db.get(AwsConnection, connection_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AWS 연결을 찾을 수 없음",
        )
    if connection.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="다른 사용자의 AWS 연결",
        )
    return connection


@router.get("", response_model=list[AwsConnectionResponse])
def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AwsConnectionResponse]:
    connections = db.scalars(
        select(AwsConnection)
        .where(AwsConnection.owner_id == user.id)
        .order_by(AwsConnection.updated_at.desc())
    ).all()
    return [_to_response(connection, db=db) for connection in connections]


@router.post("", response_model=AwsConnectionResponse, status_code=status.HTTP_201_CREATED)
def prepare_connection(
    payload: AwsConnectionPrepareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AwsConnectionResponse:
    connection = db.scalar(
        select(AwsConnection).where(
            AwsConnection.owner_id == user.id,
            AwsConnection.account_id == payload.account_id,
            AwsConnection.default_region == payload.region,
        )
    )
    if connection is None:
        import uuid

        connection = AwsConnection(
            owner_id=user.id,
            name=f"AWS {payload.account_id}",
            account_id=payload.account_id,
            default_region=payload.region,
            default_tags={},
            external_id=str(uuid.uuid4()),
            binding_status="pending_role",
        )
        db.add(connection)
    db.commit()
    db.refresh(connection)
    return _to_response(connection, db=db, include_template=True)


@router.put("/{connection_id}/role", response_model=AwsConnectionResponse)
def save_role_arn(
    connection_id: UUID,
    payload: AwsConnectionRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AwsConnectionResponse:
    connection = _owned_connection(db, connection_id, user)
    match = ROLE_ARN_RE.fullmatch(payload.role_arn.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role ARN 형식이 올바르지 않음",
        )
    if match.group("account_id") != connection.account_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 의 account_id 가 AWS 연결의 account_id 와 다름",
        )
    connection.role_arn = payload.role_arn.strip()
    connection.binding_status = "role_saved"
    connection.last_verify_error = None
    db.commit()
    db.refresh(connection)
    return _to_response(connection, db=db)


@router.post("/{connection_id}/verify", response_model=AwsVerifyResponse)
def verify_connection(
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AwsVerifyResponse:
    connection = _owned_connection(db, connection_id, user)
    if not connection.role_arn or not connection.external_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 과 External ID 가 먼저 필요",
        )

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except Exception as exc:
        return AwsVerifyResponse(
            ok=False,
            status="verify_unavailable",
            message=f"boto3 로드 실패: {exc}",
        )

    try:
        sts = boto3.client("sts")
        assumed = sts.assume_role(
            RoleArn=connection.role_arn,
            RoleSessionName=f"eolgae-verify-{connection.id}",
            ExternalId=connection.external_id,
            DurationSeconds=900,
        )
        creds = assumed["Credentials"]
        assumed_sts = boto3.client(
            "sts",
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
        identity = assumed_sts.get_caller_identity()
        if identity.get("Account") != connection.account_id:
            raise RuntimeError(
                "AssumeRole account mismatch: "
                f"expected={connection.account_id}, got={identity.get('Account')}"
            )
    except (BotoCoreError, ClientError, RuntimeError) as exc:
        connection.binding_status = "verify_failed"
        connection.last_verify_error = str(exc)
        db.commit()
        return AwsVerifyResponse(
            ok=False,
            status="verify_failed",
            message=str(exc),
        )

    connection.binding_status = "verified"
    connection.permission_mode = _permission_mode_for_verified_connection(connection)
    connection.last_verify_error = None
    connection.assumed_arn = identity.get("Arn")
    from datetime import datetime, timezone

    connection.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    return AwsVerifyResponse(
        ok=True,
        status="verified",
        message="AWS 계정 연결 검증 완료",
        assumed_arn=connection.assumed_arn,
    )


def _permission_mode_for_verified_connection(connection: AwsConnection) -> str:
    if connection.permission_mode and connection.permission_mode != "read_only":
        return connection.permission_mode
    return "plan_ready"
