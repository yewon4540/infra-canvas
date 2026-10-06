"""add canvas versions, deployments, and audit logs

Revision ID: 0010_async_plan_deployments
Revises: 0009_consolidate_canvas_columns
Create Date: 2026-06-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_async_plan_deployments"
down_revision: Union[str, Sequence[str], None] = "0009_consolidate_canvas_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canvas_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canvas_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("graph", postgresql.JSONB(), nullable=False),
        sa.Column("commit_message", sa.String(500), nullable=True),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "canvas_id",
            "version_number",
            name="uq_canvas_versions_number",
        ),
    )
    op.create_index(
        "ix_canvas_versions_canvas_id",
        "canvas_versions",
        ["canvas_id"],
    )

    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canvas_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canvas_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvas_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="plan"),
        sa.Column("aws_account_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("plan_result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("assumed_arn", sa.String(500), nullable=True),
        sa.Column(
            "initiated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','planning','success','failed')",
            name="ck_deployments_status",
        ),
        sa.CheckConstraint("mode = 'plan'", name="ck_deployments_mode"),
    )
    op.create_index("ix_deployments_canvas_id", "deployments", ["canvas_id"])
    op.create_index("ix_deployments_status", "deployments", ["status"])
    op.create_index(
        "uq_deployments_active_canvas",
        "deployments",
        ["canvas_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','planning')"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["entity_type", "entity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("uq_deployments_active_canvas", table_name="deployments")
    op.drop_index("ix_deployments_status", table_name="deployments")
    op.drop_index("ix_deployments_canvas_id", table_name="deployments")
    op.drop_table("deployments")

    op.drop_index("ix_canvas_versions_canvas_id", table_name="canvas_versions")
    op.drop_table("canvas_versions")
