from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

db_module = types.ModuleType("eolgae.db")
db_module.get_db = Mock()
db_module.SessionLocal = Mock()
sys.modules.setdefault("eolgae.db", db_module)

auth_dependencies = types.ModuleType("eolgae.auth.dependencies")
auth_dependencies.get_current_user = Mock()
sys.modules.setdefault("eolgae.auth.dependencies", auth_dependencies)

from eolgae.config import settings
from eolgae.routers.settings import get_runtime_settings


def test_runtime_settings_exposes_storage_without_secrets() -> None:
    original = {
        "artifact_store_backend": settings.artifact_store_backend,
        "artifact_retention_policy": settings.artifact_retention_policy,
        "artifact_s3_bucket": settings.artifact_s3_bucket,
        "artifact_s3_prefix": settings.artifact_s3_prefix,
        "artifact_s3_region": settings.artifact_s3_region,
        "artifact_s3_endpoint_url": settings.artifact_s3_endpoint_url,
        "artifact_s3_force_path_style": settings.artifact_s3_force_path_style,
        "artifact_s3_access_key_id": settings.artifact_s3_access_key_id,
        "artifact_s3_secret_access_key": settings.artifact_s3_secret_access_key,
    }
    try:
        settings.artifact_store_backend = "s3"
        settings.artifact_retention_policy = "keep"
        settings.artifact_s3_bucket = "eolgae-artifacts"
        settings.artifact_s3_prefix = "artifacts"
        settings.artifact_s3_region = "ap-northeast-2"
        settings.artifact_s3_endpoint_url = "http://seaweedfs:8333"
        settings.artifact_s3_force_path_style = True
        settings.artifact_s3_access_key_id = "access"
        settings.artifact_s3_secret_access_key = "secret"

        response = get_runtime_settings(user=SimpleNamespace(id="user-1"))
        payload = response.model_dump()

        assert payload["artifact_storage"]["backend"] == "s3"
        assert payload["artifact_storage"]["s3_bucket"] == "eolgae-artifacts"
        assert payload["artifact_storage"]["s3_endpoint_url"] == "http://seaweedfs:8333"
        assert "artifact_s3_access_key_id" not in payload["artifact_storage"]
        assert "artifact_s3_secret_access_key" not in payload["artifact_storage"]
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
