"""Helpers for reusable AWS account connections."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.models.aws_connection import AwsConnection
from eolgae.models.canvas import Canvas
from eolgae.models.user import User


def serialize_aws_connection(connection: AwsConnection) -> dict[str, Any]:
    return connection.as_aws_account()


def effective_aws_account(db: Session, canvas: Canvas) -> dict[str, Any]:
    """Return the AWS binding used by Plan/Apply.

    `canvas.aws_account` is kept for backward compatibility. When
    `aws_connection_id` is present, the reusable connection is authoritative.
    """
    if canvas.aws_connection_id:
        connection = db.get(AwsConnection, canvas.aws_connection_id)
        if connection is not None:
            return serialize_aws_connection(connection)
    return dict(canvas.aws_account or {})


def attach_or_create_connection(
    db: Session,
    *,
    canvas: Canvas,
    user: User,
    account_id: str,
    region: str,
) -> AwsConnection:
    connection = None
    if canvas.aws_connection_id:
        connection = db.get(AwsConnection, canvas.aws_connection_id)

    if connection is None:
        connection = db.scalar(
            select(AwsConnection).where(
                AwsConnection.owner_id == user.id,
                AwsConnection.account_id == account_id,
                AwsConnection.default_region == region,
            )
        )

    if connection is None:
        connection = AwsConnection(
            owner_id=user.id,
            name=f"AWS {account_id}",
            account_id=account_id,
            default_region=region,
            default_tags={},
            external_id=str(uuid.uuid4()),
            binding_status="pending_role",
        )
        db.add(connection)
        db.flush()
    else:
        connection.account_id = account_id
        connection.default_region = region

    canvas.aws_connection_id = connection.id
    sync_canvas_aws_account(canvas, connection)
    return connection


def sync_canvas_aws_account(canvas: Canvas, connection: AwsConnection) -> None:
    canvas.aws_account = serialize_aws_connection(connection)


def mark_connection_verified(
    *,
    canvas: Canvas,
    connection: AwsConnection,
    assumed_arn: str,
) -> None:
    connection.binding_status = "verified"
    connection.assumed_arn = assumed_arn
    connection.last_verified_at = datetime.now(timezone.utc)
    sync_canvas_aws_account(canvas, connection)
