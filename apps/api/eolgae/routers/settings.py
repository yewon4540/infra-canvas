"""User-facing application settings endpoints."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from eolgae.auth.dependencies import get_current_user
from eolgae.config import settings
from eolgae.models.user import User


router = APIRouter(prefix="/settings", tags=["settings"])


class ArtifactStorageSettings(BaseModel):
    backend: Literal["local", "s3"] | str
    retention_policy: str
    local_root: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_force_path_style: bool | None = None


class RuntimeSettingsResponse(BaseModel):
    artifact_storage: ArtifactStorageSettings


@router.get("/runtime", response_model=RuntimeSettingsResponse)
def get_runtime_settings(
    user: User = Depends(get_current_user),
) -> RuntimeSettingsResponse:
    """Return non-secret runtime settings for the authenticated user."""
    del user
    return RuntimeSettingsResponse(
        artifact_storage=ArtifactStorageSettings(
            backend=settings.artifact_store_backend,
            retention_policy=settings.artifact_retention_policy,
            local_root=(
                settings.artifact_local_root
                if settings.artifact_store_backend == "local"
                else None
            ),
            s3_bucket=settings.artifact_s3_bucket or None,
            s3_prefix=settings.artifact_s3_prefix or None,
            s3_region=settings.artifact_s3_region or None,
            s3_endpoint_url=settings.artifact_s3_endpoint_url or None,
            s3_force_path_style=settings.artifact_s3_force_path_style,
        )
    )
