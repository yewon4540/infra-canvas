"""Durable submission identity for Terrakube-owned Plan-only runs."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eolgae.models.base import Base

ACTIVE_REMOTE_PLANS = ("submitting", "unknown", "pending", "running")


class RemotePlan(Base):
    __tablename__ = "remote_plans"
    __table_args__ = (
        UniqueConstraint("canvas_id", "idempotency_key", name="uq_remote_plan_request"),
        UniqueConstraint("api_url", "organization_id", "job_id", name="uq_remote_plan_job"),
        Index("uq_remote_plan_active_canvas", "canvas_id", unique=True,
              postgresql_where=text("status IN ('submitting','unknown','pending','running')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canvas_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("canvases.id", ondelete="RESTRICT"), index=True)
    canvas_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("canvas_versions.id", ondelete="RESTRICT"))
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    canvas_revision: Mapped[str] = mapped_column(String(64))
    commit_sha: Mapped[str] = mapped_column(String(40))
    api_url: Mapped[str] = mapped_column(String(1000))
    organization_id: Mapped[str] = mapped_column(String(36))
    workspace_id: Mapped[str] = mapped_column(String(36))
    template_id: Mapped[str] = mapped_column(String(36))
    template_sha256: Mapped[str] = mapped_column(String(64))
    workspace_snapshot: Mapped[dict] = mapped_column(JSONB)
    operation: Mapped[str] = mapped_column(String(20), default="plan")
    status: Mapped[str] = mapped_column(String(30), default="submitting")
    job_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
