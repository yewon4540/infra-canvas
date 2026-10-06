"""prepare deployment approval and apply metadata

Revision ID: 0011_prepare_apply_approval
Revises: 0010_async_plan_deployments
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0011_prepare_apply_approval"
down_revision: Union[str, Sequence[str], None] = "0010_async_plan_deployments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_deployments_active_canvas", table_name="deployments")
    op.drop_constraint(
        "ck_deployments_status",
        "deployments",
        type_="check",
    )
    op.drop_constraint(
        "ck_deployments_mode",
        "deployments",
        type_="check",
    )

    op.add_column(
        "deployments",
        sa.Column("plan_artifact", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("state_backend", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("source_plan_deployment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_deployments_source_plan_deployment_id",
        "deployments",
        "deployments",
        ["source_plan_deployment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_deployments_approved_by",
        "deployments",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','approved','applying','failed')",
    )
    op.create_check_constraint(
        "ck_deployments_mode",
        "deployments",
        "mode IN ('plan','apply')",
    )
    op.create_index(
        "uq_deployments_active_canvas",
        "deployments",
        ["canvas_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','planning','applying')"),
    )


def downgrade() -> None:
    op.drop_index("uq_deployments_active_canvas", table_name="deployments")
    op.drop_constraint(
        "ck_deployments_mode",
        "deployments",
        type_="check",
    )
    op.drop_constraint(
        "ck_deployments_status",
        "deployments",
        type_="check",
    )
    op.drop_constraint(
        "fk_deployments_approved_by",
        "deployments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_deployments_source_plan_deployment_id",
        "deployments",
        type_="foreignkey",
    )

    op.drop_column("deployments", "approved_at")
    op.drop_column("deployments", "approved_by")
    op.drop_column("deployments", "source_plan_deployment_id")
    op.drop_column("deployments", "state_backend")
    op.drop_column("deployments", "plan_artifact")

    op.create_check_constraint(
        "ck_deployments_mode",
        "deployments",
        "mode = 'plan'",
    )
    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','failed')",
    )
    op.create_index(
        "uq_deployments_active_canvas",
        "deployments",
        ["canvas_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','planning')"),
    )
