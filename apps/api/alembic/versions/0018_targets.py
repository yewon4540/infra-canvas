"""add provider-neutral targets

Revision ID: 0018_targets
Revises: 0017_project_groups_environments
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0018_targets"
down_revision: Union[str, Sequence[str], None] = "0017_project_groups_environments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("aws_connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("endpoint", sa.String(length=500), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "secret_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "kind IN ('aws_account','kubernetes_cluster')",
            name="ck_targets_kind",
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending','ready','error','archived')",
            name="ck_targets_status",
        ),
        sa.ForeignKeyConstraint(["aws_connection_id"], ["aws_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_targets_owner_slug"),
    )
    op.create_index(op.f("ix_targets_owner_id"), "targets", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_targets_environment_id"),
        "targets",
        ["environment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_targets_aws_connection_id"),
        "targets",
        ["aws_connection_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_targets_aws_connection_id"), table_name="targets")
    op.drop_index(op.f("ix_targets_environment_id"), table_name="targets")
    op.drop_index(op.f("ix_targets_owner_id"), table_name="targets")
    op.drop_table("targets")
