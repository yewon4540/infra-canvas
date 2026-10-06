"""Reusable AWS account connection owned above individual canvases."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eolgae.models.base import Base


class AwsConnection(Base):
    __tablename__ = "aws_connections"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "default_region",
            name="uq_aws_connections_owner_account_region",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="AWS 계정")
    account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    default_region: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ap-northeast-2",
    )
    default_tags: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role_arn: Mapped[str | None] = mapped_column(String(500), nullable=True)
    binding_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending_role",
    )
    permission_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="read_only",
    )
    last_verify_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    assumed_arn: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def as_aws_account(self) -> dict[str, Any]:
        return {
            "aws_connection_id": str(self.id),
            "account_id": self.account_id,
            "default_region": self.default_region,
            "default_tags": self.default_tags or {},
            "external_id": self.external_id,
            "role_arn": self.role_arn,
            "binding_status": self.binding_status,
            "permission_mode": self.permission_mode,
            "last_verified_at": (
                self.last_verified_at.isoformat() if self.last_verified_at else None
            ),
            "assumed_arn": self.assumed_arn,
        }
