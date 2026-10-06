"""add refresh_tokens table

Revision ID: 0005_add_refresh_tokens
Revises: 0004_add_oauth_accounts
Create Date: 2026-05-26

Refresh token rotation + reuse detection. AUTH-SPEC §4.2.
평문 미저장 (sha256 hash 만), chain 추적 위한 replaced_by_id 자기참조 FK.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_add_refresh_tokens"
down_revision: Union[str, Sequence[str], None] = "0004_add_oauth_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_refresh_tokens_hash", "refresh_tokens", ["token_hash"]
    )
    op.create_index(
        "ix_refresh_tokens_user_created",
        "refresh_tokens",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_created", table_name="refresh_tokens")
    op.drop_constraint("uq_refresh_tokens_hash", "refresh_tokens", type_="unique")
    op.drop_table("refresh_tokens")
