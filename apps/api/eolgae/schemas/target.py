"""Schemas for provider-neutral infrastructure targets."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TargetKind = Literal["aws_account", "kubernetes_cluster"]
TargetProvider = Literal["aws", "kubernetes"]
TargetStatus = Literal["draft", "pending", "ready", "error", "archived"]


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    kind: TargetKind
    provider: TargetProvider | None = None
    environment_id: UUID | None = None
    aws_connection_id: UUID | None = None
    endpoint: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] = Field(default_factory=dict)
    secret_ref: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_kind_specific_fields(self) -> "TargetCreate":
        provider = self.provider or (
            "aws" if self.kind == "aws_account" else "kubernetes"
        )
        if self.kind == "aws_account":
            if provider != "aws":
                raise ValueError("aws_account target must use aws provider")
            if self.aws_connection_id is None:
                raise ValueError("aws_account target requires aws_connection_id")
        if self.kind == "kubernetes_cluster":
            if provider != "kubernetes":
                raise ValueError("kubernetes_cluster target must use kubernetes provider")
            if not self.endpoint:
                raise ValueError("kubernetes_cluster target requires endpoint")
        self.provider = provider
        return self


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    environment_id: UUID | None = None
    endpoint: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None
    secret_ref: dict[str, Any] | None = None
    status: TargetStatus | None = None
    archived: bool | None = None


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    slug: str
    kind: TargetKind
    provider: str
    status: TargetStatus
    environment_id: UUID | None
    aws_connection_id: UUID | None
    endpoint: str | None
    config: dict[str, Any]
    secret_ref: dict[str, Any] | None
    last_verified_at: datetime | None
    last_error: str | None
    archived_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TargetVerificationCheck(BaseModel):
    name: str
    ok: bool
    message: str


class TargetVerifyResponse(BaseModel):
    ok: bool
    mode: str
    status: TargetStatus
    message: str
    checks: list[TargetVerificationCheck]
    last_verified_at: datetime | None


class KubernetesReadOnlyManifestResponse(BaseModel):
    namespace: str
    service_account_name: str
    cluster_role_name: str
    cluster_role_binding_name: str
    manifest: str
    apply_command: str
    token_command: str
    ca_command: str
    endpoint_command: str
