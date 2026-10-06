"""add canvas kind

Revision ID: 0019_canvas_kind
Revises: 0018_targets
Create Date: 2026-07-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0019_canvas_kind"
down_revision: Union[str, Sequence[str], None] = "0018_targets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "canvases",
        sa.Column("canvas_kind", sa.String(length=50), nullable=False, server_default="aws"),
    )
    op.create_check_constraint(
        "ck_canvases_canvas_kind",
        "canvases",
        "canvas_kind IN ('aws','kubernetes','multi_architecture')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_canvases_canvas_kind", "canvases", type_="check")
    op.drop_column("canvases", "canvas_kind")
