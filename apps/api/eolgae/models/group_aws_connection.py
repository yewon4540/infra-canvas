"""Many-to-many relation between Project Groups and AWS Connections."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eolgae.models.base import Base


class GroupAwsConnection(Base):
    __tablename__ = "group_aws_connections"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canvas_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    aws_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("aws_connections.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    allowed_environments: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    permission_override: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
