"""Add the initial canvas ownership join table.

Migration 0009 later consolidates ownership into canvases.owner_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_add_canvas_owners"
down_revision: Union[str, Sequence[str], None] = "0006_add_canvas_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canvas_owners",
        sa.Column(
            "canvas_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_canvas_owners_user_id", "canvas_owners", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_canvas_owners_user_id", table_name="canvas_owners")
    op.drop_table("canvas_owners")
