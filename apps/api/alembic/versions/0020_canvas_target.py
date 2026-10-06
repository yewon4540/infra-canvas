"""add canvas target binding

Revision ID: 0020_canvas_target
Revises: 0019_canvas_kind
Create Date: 2026-07-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020_canvas_target"
down_revision: Union[str, Sequence[str], None] = "0019_canvas_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("canvases", sa.Column("target_id", sa.UUID(), nullable=True))
    op.create_index("ix_canvases_target_id", "canvases", ["target_id"])
    op.create_foreign_key(
        "fk_canvases_target_id_targets",
        "canvases",
        "targets",
        ["target_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_canvases_target_id_targets", "canvases", type_="foreignkey")
    op.drop_index("ix_canvases_target_id", table_name="canvases")
    op.drop_column("canvases", "target_id")
