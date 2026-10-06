"""promote aws account binding to reusable connections

Revision ID: 0015_aws_connections
Revises: 0014_plan_progress_events
Create Date: 2026-06-26
"""
import uuid
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text


revision: str = "0015_aws_connections"
down_revision: Union[str, Sequence[str], None] = "0014_plan_progress_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aws_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("account_id", sa.String(length=12), nullable=False),
        sa.Column("default_region", sa.String(length=50), nullable=False),
        sa.Column(
            "default_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("role_arn", sa.String(length=500), nullable=True),
        sa.Column("binding_status", sa.String(length=50), nullable=False),
        sa.Column("assumed_arn", sa.String(length=500), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "account_id",
            "default_region",
            name="uq_aws_connections_owner_account_region",
        ),
    )
    op.create_index(
        op.f("ix_aws_connections_owner_id"),
        "aws_connections",
        ["owner_id"],
        unique=False,
    )
    op.add_column(
        "canvases",
        sa.Column("aws_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_canvases_aws_connection_id"),
        "canvases",
        ["aws_connection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_canvases_aws_connection_id",
        "canvases",
        "aws_connections",
        ["aws_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    rows = bind.execute(
        text(
            """
            SELECT DISTINCT ON (
                c.owner_id,
                c.aws_account->>'account_id',
                COALESCE(c.aws_account->>'default_region', 'ap-northeast-2')
            )
                c.owner_id,
                c.aws_account->>'account_id' AS account_id,
                COALESCE(c.aws_account->>'default_region', 'ap-northeast-2')
                    AS default_region,
                COALESCE(c.aws_account->'default_tags', '{}'::jsonb) AS default_tags,
                c.aws_account->>'external_id' AS external_id,
                c.aws_account->>'role_arn' AS role_arn,
                COALESCE(c.aws_account->>'binding_status', 'pending_role')
                    AS binding_status,
                c.aws_account->>'assumed_arn' AS assumed_arn,
                NULLIF(c.aws_account->>'last_verified_at', '')::timestamptz
                    AS last_verified_at,
                COALESCE(c.created_at, now()) AS created_at,
                COALESCE(c.updated_at, now()) AS updated_at
            FROM canvases c
            WHERE c.owner_id IS NOT NULL
              AND c.aws_account IS NOT NULL
              AND c.aws_account ? 'account_id'
              AND c.aws_account ? 'external_id'
            ORDER BY
                c.owner_id,
                c.aws_account->>'account_id',
                COALESCE(c.aws_account->>'default_region', 'ap-northeast-2'),
                c.updated_at DESC
            """
        )
    ).mappings()

    for row in rows:
        bind.execute(
            text(
                """
                INSERT INTO aws_connections (
                    id,
                    owner_id,
                    name,
                    account_id,
                    default_region,
                    default_tags,
                    external_id,
                    role_arn,
                    binding_status,
                    assumed_arn,
                    last_verified_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :owner_id,
                    :name,
                    :account_id,
                    :default_region,
                    CAST(:default_tags AS jsonb),
                    :external_id,
                    :role_arn,
                    :binding_status,
                    :assumed_arn,
                    :last_verified_at,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                **row,
                "id": str(uuid.uuid4()),
                "name": f"AWS {row['account_id']}",
                "default_tags": json.dumps(row["default_tags"] or {}),
            },
        )
    bind.execute(
        text(
            """
            UPDATE canvases c
            SET aws_connection_id = ac.id
            FROM aws_connections ac
            WHERE c.owner_id = ac.owner_id
              AND c.aws_account IS NOT NULL
              AND c.aws_account->>'account_id' = ac.account_id
              AND COALESCE(c.aws_account->>'default_region', 'ap-northeast-2') =
                  ac.default_region
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_canvases_aws_connection_id", "canvases", type_="foreignkey")
    op.drop_index(op.f("ix_canvases_aws_connection_id"), table_name="canvases")
    op.drop_column("canvases", "aws_connection_id")
    op.drop_index(op.f("ix_aws_connections_owner_id"), table_name="aws_connections")
    op.drop_table("aws_connections")
