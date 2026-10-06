"""add destroy deployment mode and statuses

Revision ID: 0016_destroy_deployments
Revises: 0015_aws_connections
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_destroy_deployments"
down_revision: Union[str, Sequence[str], None] = "0015_aws_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_deployments_active_canvas", table_name="deployments")
    op.drop_constraint("ck_deployments_status", "deployments", type_="check")
    op.drop_constraint("ck_deployments_mode", "deployments", type_="check")

    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','approved','applying','applied','destroying','destroyed','failed')",
    )
    op.create_check_constraint(
        "ck_deployments_mode",
        "deployments",
        "mode IN ('plan','apply','destroy')",
    )
    op.create_index(
        "uq_deployments_active_canvas",
        "deployments",
        ["canvas_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued','planning','applying','destroying')"
        ),
    )
    op.create_index(
        "uq_deployments_destroy_source_plan",
        "deployments",
        ["source_plan_deployment_id"],
        unique=True,
        postgresql_where=sa.text(
            "mode = 'destroy' AND source_plan_deployment_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_deployments_destroy_source_plan", table_name="deployments")
    op.drop_index("uq_deployments_active_canvas", table_name="deployments")
    op.drop_constraint("ck_deployments_mode", "deployments", type_="check")
    op.drop_constraint("ck_deployments_status", "deployments", type_="check")

    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','approved','applying','applied','failed')",
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
