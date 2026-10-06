"""Canvas snapshots, asynchronous Plan jobs, and deployment audit records."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eolgae.models.base import Base


class CanvasVersion(Base):
    __tablename__ = "canvas_versions"
    __table_args__ = (
        UniqueConstraint(
            "canvas_id",
            "version_number",
            name="uq_canvas_versions_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    canvas_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canvases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    graph: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    commit_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','planning','success','approved','applying','applied','destroying','destroyed','failed')",
            name="ck_deployments_status",
        ),
        CheckConstraint("mode IN ('plan','apply','destroy')", name="ck_deployments_mode"),
        Index("ix_deployments_canvas_id", "canvas_id"),
        Index("ix_deployments_status", "status"),
        Index(
            "uq_deployments_active_canvas",
            "canvas_id",
            unique=True,
            postgresql_where=text("status IN ('queued','planning','applying','destroying')"),
        ),
        Index(
            "uq_deployments_apply_source_plan",
            "source_plan_deployment_id",
            unique=True,
            postgresql_where=text(
                "mode = 'apply' AND source_plan_deployment_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_deployments_destroy_source_plan",
            "source_plan_deployment_id",
            unique=True,
            postgresql_where=text(
                "mode = 'destroy' AND source_plan_deployment_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    canvas_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canvases.id", ondelete="CASCADE"),
        nullable=False,
    )
    canvas_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canvas_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="plan",
    )
    aws_account_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    plan_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    plan_artifact: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    state_backend: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    progress_events: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumed_arn: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_plan_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index(
            "ix_audit_logs_entity",
            "entity_type",
            "entity_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
