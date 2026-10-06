"""canvas soft delete

Revision ID: 0002_canvas_soft_delete
Revises: 0001_initial_canvas
Create Date: 2026-05-22

`deleted_at` 컬럼 추가. null 이면 미삭제, 값이 있으면 휴지통 상태.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_canvas_soft_delete"
down_revision: Union[str, Sequence[str], None] = "0001_initial_canvas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "canvases",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_canvases_deleted_at",
        "canvases",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_canvases_deleted_at", table_name="canvases")
    op.drop_column("canvases", "deleted_at")
