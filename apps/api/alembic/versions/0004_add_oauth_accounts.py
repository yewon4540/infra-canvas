"""add oauth_accounts table

Revision ID: 0004_add_oauth_accounts
Revises: 0003_add_users
Create Date: 2026-05-26

GitHub/Google 등 OAuth provider 매핑. ADR 017 §oauth_accounts 테이블 신설.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_add_oauth_accounts"
down_revision: Union[str, Sequence[str], None] = "0003_add_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("email_at_provider", sa.String(255), nullable=True),
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
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_oauth_provider_uid"
        ),
    )
    op.create_index(
        "ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
