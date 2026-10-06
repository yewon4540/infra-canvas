"""Deployment artifact storage."""
from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from uuid import UUID

from eolgae.config import settings


@dataclass(frozen=True)
class StoredArtifact:
    kind: str
    filename: str
    storage_uri: str
    sha256: str
    size_bytes: int
    content_type: str
    backend: str
    retention_policy: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "filename": self.filename,
            "storage_uri": self.storage_uri,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "backend": self.backend,
            "retention_policy": self.retention_policy,
        }


class ArtifactStore:
    backend = "base"

    def put_bytes(
        self,
        *,
        canvas_id: str,
        deployment_id: str,
        kind: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredArtifact:
        raise NotImplementedError

    def get_bytes(self, metadata: dict[str, Any]) -> bytes:
        raise NotImplementedError


class LocalArtifactStore(ArtifactStore):
    backend = "local"

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        retention_policy: str | None = None,
    ) -> None:
        self.root = Path(root or settings.artifact_local_root).expanduser().resolve()
        self.retention_policy = retention_policy or settings.artifact_retention_policy

    def put_bytes(
        self,
        *,
        canvas_id: str,
        deployment_id: str,
        kind: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredArtifact:
        safe_filename = Path(filename).name
        path = self.root / "canvases" / canvas_id / "deployments" / deployment_id / safe_filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredArtifact(
            kind=kind,
            filename=safe_filename,
            storage_uri=path.as_uri(),
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type
            or mimetypes.guess_type(safe_filename)[0]
            or "application/octet-stream",
            backend=self.backend,
            retention_policy=self.retention_policy,
        )

    def get_bytes(self, metadata: dict[str, Any]) -> bytes:
        uri = metadata.get("storage_uri")
        if not isinstance(uri, str) or not uri.startswith("file://"):
            raise ValueError("local artifact storage_uri가 file:// 형식이 아님")
        parsed = urlparse(uri)
        path = Path(unquote(parsed.path))
        if not path.is_file():
            raise FileNotFoundError(f"artifact not found: {path}")
        data = path.read_bytes()
        expected_sha = metadata.get("sha256")
        if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError("artifact checksum 불일치")
        return data


class S3ArtifactStore(ArtifactStore):
    backend = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        prefix: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
        force_path_style: bool | None = None,
        retention_policy: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.bucket = bucket or settings.artifact_s3_bucket
        if not self.bucket:
            raise RuntimeError("ARTIFACT_S3_BUCKET 설정이 필요")
        self.prefix = (prefix if prefix is not None else settings.artifact_s3_prefix).strip("/")
        self.region = region or settings.artifact_s3_region
        self.endpoint_url = endpoint_url if endpoint_url is not None else settings.artifact_s3_endpoint_url
        self.retention_policy = retention_policy or settings.artifact_retention_policy
        self.client = client or self._build_client(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            force_path_style=force_path_style,
        )

    def put_bytes(
        self,
        *,
        canvas_id: str,
        deployment_id: str,
        kind: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredArtifact:
        safe_filename = Path(filename).name
        object_key = self._object_key(
            canvas_id=canvas_id,
            deployment_id=deployment_id,
            filename=safe_filename,
        )
        digest = hashlib.sha256(data).hexdigest()
        resolved_content_type = (
            content_type
            or mimetypes.guess_type(safe_filename)[0]
            or "application/octet-stream"
        )
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=data,
            ContentType=resolved_content_type,
            Metadata={
                "sha256": digest,
                "kind": kind,
                "retention-policy": self.retention_policy,
            },
        )
        return StoredArtifact(
            kind=kind,
            filename=safe_filename,
            storage_uri=f"s3://{self.bucket}/{quote(object_key)}",
            sha256=digest,
            size_bytes=len(data),
            content_type=resolved_content_type,
            backend=self.backend,
            retention_policy=self.retention_policy,
        )

    def get_bytes(self, metadata: dict[str, Any]) -> bytes:
        uri = metadata.get("storage_uri")
        if not isinstance(uri, str) or not uri.startswith("s3://"):
            raise ValueError("s3 artifact storage_uri가 s3:// 형식이 아님")
        bucket, object_key = _parse_s3_uri(uri)
        response = self.client.get_object(Bucket=bucket, Key=object_key)
        body = response["Body"]
        data = body.read()
        expected_sha = metadata.get("sha256")
        if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError("artifact checksum 불일치")
        return data

    def _object_key(
        self,
        *,
        canvas_id: str,
        deployment_id: str,
        filename: str,
    ) -> str:
        parts = [
            self.prefix,
            "canvases",
            canvas_id,
            "deployments",
            deployment_id,
            filename,
        ]
        return "/".join(part for part in parts if part)

    def _build_client(
        self,
        *,
        access_key_id: str | None,
        secret_access_key: str | None,
        session_token: str | None,
        force_path_style: bool | None,
    ):
        import boto3
        from botocore.config import Config

        resolved_access_key = access_key_id or settings.artifact_s3_access_key_id or None
        resolved_secret_key = secret_access_key or settings.artifact_s3_secret_access_key or None
        resolved_session_token = session_token or settings.artifact_s3_session_token or None
        use_path_style = (
            settings.artifact_s3_force_path_style
            if force_path_style is None
            else force_path_style
        )
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region,
            "endpoint_url": self.endpoint_url or None,
            "config": Config(
                s3={"addressing_style": "path" if use_path_style else "auto"}
            ),
        }
        if resolved_access_key and resolved_secret_key:
            kwargs["aws_access_key_id"] = resolved_access_key
            kwargs["aws_secret_access_key"] = resolved_secret_key
        if resolved_session_token:
            kwargs["aws_session_token"] = resolved_session_token
        return boto3.client(**kwargs)


def get_artifact_store() -> ArtifactStore:
    if settings.artifact_store_backend == "local":
        return LocalArtifactStore()
    if settings.artifact_store_backend == "s3":
        return S3ArtifactStore()
    raise RuntimeError(f"지원하지 않는 artifact store backend: {settings.artifact_store_backend}")


def deployment_artifact_prefix(
    *,
    canvas_id: str | UUID,
    deployment_id: str | UUID,
) -> dict[str, str]:
    return {
        "canvas_id": str(canvas_id),
        "deployment_id": str(deployment_id),
    }


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    bucket = parsed.netloc
    object_key = unquote(parsed.path.lstrip("/"))
    if not bucket or not object_key:
        raise ValueError("s3 artifact storage_uri가 불완전함")
    return bucket, object_key
