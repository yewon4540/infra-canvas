"""initial canvas table

Revision ID: 0001_initial_canvas
Revises:
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_canvas"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canvases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, server_default="Untitled"),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="0.1.0"),
        sa.Column("state", sa.String(20), nullable=False, server_default="design"),
        sa.Column("graph", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("aws_account", postgresql.JSONB, nullable=True),
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
    )


def downgrade() -> None:
    op.drop_table("canvases")
