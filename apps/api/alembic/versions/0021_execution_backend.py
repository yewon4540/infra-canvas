"""Separate canvas execution ownership from installed capabilities."""
from alembic import op
import sqlalchemy as sa

revision = "0021_execution_backend"
down_revision = "0020_canvas_target"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("canvases", sa.Column("execution_backend", sa.String(20),
                  nullable=False, server_default="eolgae_direct"))
    op.add_column("canvases", sa.Column("terrakube_workspace_id", sa.String(36)))
    op.create_check_constraint("ck_canvas_execution_binding", "canvases",
        "(execution_backend = 'eolgae_direct' AND terrakube_workspace_id IS NULL) OR "
        "(execution_backend = 'terrakube' AND terrakube_workspace_id IS NOT NULL)")
    op.create_index("uq_canvas_terrakube_workspace", "canvases",
                    ["terrakube_workspace_id"], unique=True)


def downgrade():
    op.drop_index("uq_canvas_terrakube_workspace", table_name="canvases")
    op.drop_constraint("ck_canvas_execution_binding", "canvases", type_="check")
    op.drop_column("canvases", "terrakube_workspace_id")
    op.drop_column("canvases", "execution_backend")
