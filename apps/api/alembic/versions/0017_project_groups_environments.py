"""add project groups, environments, and group aws connections

Revision ID: 0017_project_groups_environments
Revises: 0016_destroy_deployments
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text


revision: str = "0017_project_groups_environments"
down_revision: Union[str, Sequence[str], None] = "0016_destroy_deployments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aws_connections",
        sa.Column(
            "permission_mode",
            sa.String(length=50),
            nullable=False,
            server_default="read_only",
        ),
    )
    op.add_column(
        "aws_connections",
        sa.Column("last_verify_error", sa.String(length=1000), nullable=True),
    )

    op.create_table(
        "environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "risk_level IN ('low','medium','high')",
            name="ck_environments_risk_level",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_environments_owner_slug"),
    )
    op.create_index(
        op.f("ix_environments_owner_id"),
        "environments",
        ["owner_id"],
        unique=False,
    )

    op.add_column("canvas_groups", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column(
        "canvas_groups",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "canvas_groups",
        sa.Column("default_environment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_canvas_groups_status",
        "canvas_groups",
        "status IN ('active','archived')",
    )
    op.create_index(
        "ix_canvas_groups_default_environment_id",
        "canvas_groups",
        ["default_environment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_canvas_groups_default_environment_id",
        "canvas_groups",
        "environments",
        ["default_environment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "group_aws_connections",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aws_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "allowed_environments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("permission_override", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["canvas_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["aws_connection_id"],
            ["aws_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "aws_connection_id"),
    )
    op.create_index(
        "ix_group_aws_connections_aws_connection_id",
        "group_aws_connections",
        ["aws_connection_id"],
        unique=False,
    )
    op.create_index(
        "uq_group_aws_connections_default",
        "group_aws_connections",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )

    op.add_column(
        "canvases",
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_canvases_environment_id"),
        "canvases",
        ["environment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_canvases_environment_id",
        "canvases",
        "environments",
        ["environment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    bind.execute(
        text(
            """
            INSERT INTO environments (
                id, owner_id, name, slug, description, risk_level, sort_order
            )
            SELECT gen_random_uuid(), u.id, seed.name, seed.slug, seed.description,
                   seed.risk_level, seed.sort_order
            FROM users u
            CROSS JOIN (
                VALUES
                    ('Development', 'dev', '개발/실험 환경', 'low', 10),
                    ('Staging', 'stg', '운영 반영 전 검증 환경', 'medium', 20),
                    ('Production', 'prd', '운영 환경', 'high', 30),
                    ('Shared', 'shared', '공유 인프라 환경', 'medium', 40),
                    ('Sandbox', 'sandbox', '임시 테스트 환경', 'low', 50)
            ) AS seed(name, slug, description, risk_level, sort_order)
            ON CONFLICT (owner_id, slug) DO NOTHING
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE canvas_groups cg
            SET slug = trim(
                    both '-' from lower(regexp_replace(cg.name, '[^a-zA-Z0-9]+', '-', 'g'))
                ) || '-' || left(cg.id::text, 8),
                default_environment_id = env.id
            FROM environments env
            WHERE env.owner_id = cg.owner_id
              AND env.slug = 'dev'
              AND cg.slug IS NULL
            """
        )
    )
    bind.execute(
        text(
            """
            UPDATE canvas_groups
            SET slug = 'group-' || id::text
            WHERE slug IS NULL OR slug = ''
            """
        )
    )
    op.alter_column("canvas_groups", "slug", nullable=False)
    op.create_unique_constraint(
        "uq_canvas_groups_owner_slug",
        "canvas_groups",
        ["owner_id", "slug"],
    )
    bind.execute(
        text(
            """
            UPDATE canvases c
            SET environment_id = cg.default_environment_id
            FROM canvas_groups cg
            WHERE c.group_id = cg.id
              AND c.environment_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("aws_connections", "last_verify_error")
    op.drop_column("aws_connections", "permission_mode")

    op.drop_constraint("fk_canvases_environment_id", "canvases", type_="foreignkey")
    op.drop_index(op.f("ix_canvases_environment_id"), table_name="canvases")
    op.drop_column("canvases", "environment_id")

    op.drop_index("uq_group_aws_connections_default", table_name="group_aws_connections")
    op.drop_index(
        "ix_group_aws_connections_aws_connection_id",
        table_name="group_aws_connections",
    )
    op.drop_table("group_aws_connections")

    op.drop_constraint(
        "fk_canvas_groups_default_environment_id",
        "canvas_groups",
        type_="foreignkey",
    )
    op.drop_index("ix_canvas_groups_default_environment_id", table_name="canvas_groups")
    op.drop_constraint("ck_canvas_groups_status", "canvas_groups", type_="check")
    op.drop_constraint("uq_canvas_groups_owner_slug", "canvas_groups", type_="unique")
    op.drop_column("canvas_groups", "default_environment_id")
    op.drop_column("canvas_groups", "status")
    op.drop_column("canvas_groups", "slug")

    op.drop_index(op.f("ix_environments_owner_id"), table_name="environments")
    op.drop_table("environments")
