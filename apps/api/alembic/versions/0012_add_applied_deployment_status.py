"""add applied deployment status

Revision ID: 0012_add_applied_status
Revises: 0011_prepare_apply_approval
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0012_add_applied_status"
down_revision: Union[str, Sequence[str], None] = "0011_prepare_apply_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_deployments_status",
        "deployments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','approved','applying','applied','failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_deployments_status",
        "deployments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_deployments_status",
        "deployments",
        "status IN ('queued','planning','success','approved','applying','failed')",
    )
