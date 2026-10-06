"""enforce single-use apply source plans

Revision ID: 0013_single_use_apply
Revises: 0012_add_applied_status
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_single_use_apply"
down_revision: Union[str, Sequence[str], None] = "0012_add_applied_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            """
            SELECT source_plan_deployment_id, count(*) AS apply_count
            FROM deployments
            WHERE mode = 'apply'
              AND source_plan_deployment_id IS NOT NULL
            GROUP BY source_plan_deployment_id
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot apply 0013_single_use_apply: duplicate Apply deployments "
            f"exist for source_plan_deployment_id={duplicate.source_plan_deployment_id}. "
            "Delete or archive duplicate Apply rows before running this migration."
        )

    op.create_index(
        "uq_deployments_apply_source_plan",
        "deployments",
        ["source_plan_deployment_id"],
        unique=True,
        postgresql_where=sa.text(
            "mode = 'apply' AND source_plan_deployment_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_deployments_apply_source_plan", table_name="deployments")
