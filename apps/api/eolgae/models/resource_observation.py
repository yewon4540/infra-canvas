"""Bounded normalized observations and explicit execution context links."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from eolgae.models.base import Base


class ResourceObservation(Base):
    __tablename__ = 'resource_observations'
    __table_args__ = (Index('ix_resource_observations_scope', 'target_id', 'scope_key', 'created_at'),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('targets.id', ondelete='CASCADE'))
    scope_key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResourceExecutionLink(Base):
    __tablename__ = 'resource_execution_links'
    __table_args__ = (UniqueConstraint('target_id', 'scope_key', 'resource_uid', name='uq_resource_execution_link'),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('targets.id', ondelete='CASCADE'))
    scope_key: Mapped[str] = mapped_column(String(64))
    resource_uid: Mapped[str] = mapped_column(String(300))
    canvas_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('canvases.id', ondelete='CASCADE'))
    linked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
