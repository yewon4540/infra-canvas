"""Canvas ORM model — single table with JSONB graph column."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eolgae.models.base import Base


class Canvas(Base):
    __tablename__ = "canvases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="Untitled")
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="0.1.0")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="design")
    canvas_kind: Mapped[str] = mapped_column(String(50), nullable=False, default="aws")
    graph: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    aws_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("aws_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    aws_account: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Soft delete — null 이면 미삭제, 채워지면 휴지통 상태
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Ownership / group — 0009 에서 조인 테이블 흡수. owner_id 는 NULLABLE
    # (인증 도입 이전 캔버스는 owner 없음 — 첫 접근 시 자동 claim).
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canvas_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
