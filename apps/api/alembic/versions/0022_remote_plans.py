"""Persist remote Plan submission identity and reconciliation state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_remote_plans"
down_revision = "0021_execution_backend"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("remote_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canvas_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canvases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canvas_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canvas_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("initiated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        *[sa.Column(name, sa.String(size), nullable=False) for name, size in [
            ("canvas_revision",64), ("commit_sha",40), ("api_url",1000), ("organization_id",36),
            ("workspace_id",36), ("template_id",36), ("template_sha256",64), ("operation",20), ("status",30)]],
        sa.Column("workspace_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("job_id",sa.String(30), nullable=True),
        sa.Column("result",postgresql.JSONB(),nullable=True),
        sa.Column("error_message",sa.String(500),nullable=True),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("canvas_id","idempotency_key",name="uq_remote_plan_request"),
        sa.UniqueConstraint("api_url","organization_id","job_id",name="uq_remote_plan_job"),
    )
    op.create_index("ix_remote_plans_canvas_id","remote_plans",["canvas_id"])
    op.create_index("uq_remote_plan_active_canvas","remote_plans",["canvas_id"],unique=True,
                    postgresql_where=sa.text("status IN ('submitting','unknown','pending','running')"))


def downgrade():
    op.drop_table("remote_plans")
