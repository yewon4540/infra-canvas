"""Pydantic schemas for /groups router. CANVAS-GROUP-SPEC.md §3 따름."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CanvasGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=20)
    default_environment_id: UUID | None = None
    sort_order: int = 0


class CanvasGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    default_environment_id: UUID | None = None
    sort_order: int | None = None


class GroupAwsConnectionSummary(BaseModel):
    id: UUID
    name: str
    account_id: str
    default_region: str
    binding_status: str
    permission_mode: str
    is_default: bool = False


class EnvironmentSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    risk_level: str


class CanvasGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    slug: str
    description: str | None
    color: str | None
    status: str = "active"
    default_environment_id: UUID | None = None
    default_environment: EnvironmentSummary | None = None
    default_aws_connection: GroupAwsConnectionSummary | None = None
    connected_aws_connections: list[GroupAwsConnectionSummary] = Field(default_factory=list)
    canvas_count: int = 0
    last_activity_at: datetime | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class GroupAwsConnectionAttach(BaseModel):
    aws_connection_id: UUID
    is_default: bool = False


class CanvasOwnerResponse(BaseModel):
    # 0009 흡수 후 — canvases.owner_id 컬럼 기반. 조인테이블의 claimed_at 은 제거됨.
    model_config = ConfigDict(from_attributes=True)

    canvas_id: UUID
    owner_id: UUID


class CanvasInGroupResponse(BaseModel):
    """그룹 내 캔버스 목록 응답 — Canvas 모델의 일부 필드만."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    state: str
    updated_at: datetime
    deleted_at: datetime | None
