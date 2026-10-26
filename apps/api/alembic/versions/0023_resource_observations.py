"""Persist normalized observations and explicit execution context links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = '0023_resource_observations'
down_revision = '0022_remote_plans'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('resource_observations', 'resource_execution_links'):
        columns = [sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
                   sa.Column('target_id', pg.UUID(as_uuid=True), sa.ForeignKey('targets.id', ondelete='CASCADE'), nullable=False),
                   sa.Column('scope_key', sa.String(64), nullable=False),
                   sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]
        if table == 'resource_observations':
            columns.append(sa.Column('payload', pg.JSONB(), nullable=False))
        else:
            columns.extend([
                sa.Column('resource_uid', sa.String(300), nullable=False),
                sa.Column('canvas_id', pg.UUID(as_uuid=True), sa.ForeignKey('canvases.id', ondelete='CASCADE'), nullable=False),
                sa.Column('linked_by', pg.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
                sa.UniqueConstraint('target_id', 'scope_key', 'resource_uid', name='uq_resource_execution_link')])
        op.create_table(table, *columns)
    op.create_index('ix_resource_observations_scope', 'resource_observations', ['target_id', 'scope_key', 'created_at'])


def downgrade():
    op.drop_table('resource_execution_links')
    op.drop_table('resource_observations')
