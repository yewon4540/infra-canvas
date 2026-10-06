"""consolidate canvas owner/group join tables into canvases columns

Revision ID: 0009_consolidate_canvas_columns
Revises: 0008_canvas_group_memberships
Create Date: 2026-05-28

활성 마이그레이션: 임시 owner/group 조인 테이블을 canvases 컬럼으로 통합한다.

주의: owner_id 는 *NULLABLE* 로 추가한다. 인증 도입 이전에 만들어진
캔버스(미 claim)는 owner 가 없기 때문. NOT NULL 강제는 모든 캔버스의
owner 가 채워진 뒤 별도 후속 마이그레이션에서 수행한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_consolidate_canvas_columns"
down_revision: Union[str, Sequence[str], None] = "0008_canvas_group_memberships"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. canvases.owner_id 컬럼화 ---
    op.add_column(
        "canvases",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # canvas_owners → canvases.owner_id 백필
    op.execute(
        """
        UPDATE canvases
           SET owner_id = co.user_id
          FROM canvas_owners co
         WHERE canvases.id = co.canvas_id
        """
    )
    op.create_foreign_key(
        "fk_canvases_owner",
        "canvases",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_canvases_owner_id", "canvases", ["owner_id"])

    # --- 2. canvases.group_id 컬럼화 ---
    op.add_column(
        "canvases",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # canvas_group_memberships → canvases.group_id 백필
    op.execute(
        """
        UPDATE canvases
           SET group_id = cgm.group_id
          FROM canvas_group_memberships cgm
         WHERE canvases.id = cgm.canvas_id
        """
    )
    op.create_foreign_key(
        "fk_canvases_group",
        "canvases",
        "canvas_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_canvases_group_id", "canvases", ["group_id"])

    # --- 3. 임시 조인 테이블 제거 ---
    op.drop_index("ix_cgm_group_id", table_name="canvas_group_memberships")
    op.drop_table("canvas_group_memberships")
    op.drop_index("ix_canvas_owners_user_id", table_name="canvas_owners")
    op.drop_table("canvas_owners")


def downgrade() -> None:
    # --- 3'. 조인 테이블 복원 (0007 / 0008 정의와 동일) ---
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
    op.create_index("ix_cgm_group_id", "canvas_group_memberships", ["group_id"])

    # 컬럼 → 조인 테이블 역백필
    op.execute(
        """
        INSERT INTO canvas_owners (canvas_id, user_id)
        SELECT id, owner_id FROM canvases WHERE owner_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO canvas_group_memberships (canvas_id, group_id, added_by)
        SELECT c.id, c.group_id, c.owner_id
          FROM canvases c
         WHERE c.group_id IS NOT NULL AND c.owner_id IS NOT NULL
        """
    )

    # --- 2' / 1'. 컬럼 제거 ---
    op.drop_index("ix_canvases_group_id", table_name="canvases")
    op.drop_constraint("fk_canvases_group", "canvases", type_="foreignkey")
    op.drop_column("canvases", "group_id")

    op.drop_index("ix_canvases_owner_id", table_name="canvases")
    op.drop_constraint("fk_canvases_owner", "canvases", type_="foreignkey")
    op.drop_column("canvases", "owner_id")
