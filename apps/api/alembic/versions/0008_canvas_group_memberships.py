"""add canvas_group_memberships join table

Revision ID: 0008_canvas_group_memberships
Revises: 0007_add_canvas_owners
Create Date: 2026-05-26

캔버스 ↔ 그룹 매핑. canvas_id 가 PK 라 1캔버스 = 1그룹 강제.
CANVAS-GROUP-SPEC §2.2 / §7.2.

NOTE: revision ID 가 32자 (alembic_version.version_num 기본 VARCHAR(32) 제약).
같은 표를 따르는 다른 revision 도 모두 32자 이내로 명명.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0008_canvas_group_memberships"
down_revision: Union[str, Sequence[str], None] = "0007_add_canvas_owners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canvas_group_memberships",
        sa.Column(
            "canvas_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canvas_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "added_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cgm_group_id", "canvas_group_memberships", ["group_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_cgm_group_id", table_name="canvas_group_memberships")
    op.drop_table("canvas_group_memberships")
