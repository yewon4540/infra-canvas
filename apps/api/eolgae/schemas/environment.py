"""Schemas for Project Environments."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    risk_level: RiskLevel = "low"
    sort_order: int = 0


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    risk_level: RiskLevel | None = None
    sort_order: int | None = None
    archived: bool | None = None


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    slug: str
    description: str | None
    risk_level: RiskLevel
    sort_order: int
    archived_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
