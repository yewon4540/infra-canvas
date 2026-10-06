"""Schemas for asynchronous OpenTofu Plan jobs."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


DeploymentStatus = Literal[
    "queued",
    "planning",
    "success",
    "approved",
    "applying",
    "applied",
    "destroying",
    "destroyed",
    "failed",
]


class DeploymentResponse(BaseModel):
    id: UUID
    canvas_id: UUID
    canvas_version_id: UUID
    status: DeploymentStatus
    mode: Literal["plan", "apply", "destroy"]
    plan_result: dict[str, Any] | None = None
    plan_artifact: dict[str, Any] | None = None
    state_backend: dict[str, Any] | None = None
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    assumed_arn: str | None = None
    source_plan_deployment_id: UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("plan_artifact")
    def serialize_plan_artifact(
        self,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not value:
            return None
        return _artifact_summary(value)

    @field_serializer("plan_result")
    def serialize_plan_result(
        self,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not value:
            return None
        result = dict(value)
        if result.get("plan_artifact"):
            result["plan_artifact"] = _artifact_summary(result["plan_artifact"])
        return result


def _artifact_summary(value: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: value.get(key)
        for key in ("format", "filename", "sha256", "size_bytes")
        if key in value
    }
    storage = value.get("storage")
    if isinstance(storage, dict):
        summary["storage"] = {
            key: storage.get(key)
            for key in ("backend", "retention_policy")
            if key in storage
        }
    return summary
