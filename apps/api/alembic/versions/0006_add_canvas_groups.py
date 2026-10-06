"""add canvas_groups table

Revision ID: 0006_add_canvas_groups
Revises: 0005_add_refresh_tokens
Create Date: 2026-05-26

캔버스 폴더. CANVAS-GROUP-SPEC §2.1.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_add_canvas_groups"
down_revision: Union[str, Sequence[str], None] = "0005_add_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canvas_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_canvas_groups_owner_sort",
        "canvas_groups",
        ["owner_id", "sort_order"],
    )
    op.create_index(
        "ix_canvas_groups_deleted_at",
        "canvas_groups",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_canvas_groups_deleted_at", table_name="canvas_groups")
    op.drop_index("ix_canvas_groups_owner_sort", table_name="canvas_groups")
    op.drop_table("canvas_groups")
