"""Target verification helpers.

Kubernetes live checks intentionally stop before kube API access until the
Kubernetes client/dry-run adapter is added. Secret reference resolution is still
checked here so later inventory and dry-run code can share the same boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eolgae.models.aws_connection import AwsConnection
from eolgae.models.target import Target
from eolgae.schemas.target import TargetVerificationCheck
from eolgae.services.target_secrets import resolve_kubernetes_credentials


@dataclass(frozen=True)
class TargetVerification:
    ok: bool
    mode: str
    status: str
    message: str
    last_error: str | None
    checks: list[TargetVerificationCheck]


def verify_aws_target(connection: AwsConnection | None) -> TargetVerification:
    connection_ok = connection is not None and connection.binding_status == "verified"
    checks = [
        TargetVerificationCheck(
            name="aws_connection",
            ok=connection_ok,
            message=(
                "AWS Connection is verified"
                if connection_ok
                else "AWS Connection is missing or not verified"
            ),
        )
    ]
    return TargetVerification(
        ok=connection_ok,
        mode="aws_connection",
        status="ready" if connection_ok else "error",
        message=(
            "AWS target is ready"
            if connection_ok
            else "Verify the AWS Connection before using this target"
        ),
        last_error=None if connection_ok else "AWS Connection is not verified",
        checks=checks,
    )


def verify_kubernetes_target_metadata(target: Target) -> TargetVerification:
    config: dict[str, Any] = target.config or {}
    secret_ref: dict[str, Any] = target.secret_ref or {}

    endpoint_ok = bool(target.endpoint and target.endpoint.startswith("https://"))
    namespace_ok = bool(config.get("default_namespace") or "default")
    secret_ok = bool(secret_ref.get("name"))
    secret_resolution = resolve_kubernetes_credentials(
        endpoint=target.endpoint,
        config=config,
        secret_ref=secret_ref,
    )
    secret_backend_ok = secret_resolution.ok
    live_cluster_ok = False

    checks = [
        TargetVerificationCheck(
            name="endpoint",
            ok=endpoint_ok,
            message=(
                "Kubernetes API endpoint is present"
                if endpoint_ok
                else "Kubernetes API endpoint must start with https://"
            ),
        ),
        TargetVerificationCheck(
            name="default_namespace",
            ok=namespace_ok,
            message="Default namespace is configured",
        ),
        TargetVerificationCheck(
            name="secret_ref",
            ok=secret_ok,
            message=(
                "kubeconfig/service account secret reference is present"
                if secret_ok
                else "Secret reference is required before live verification"
            ),
        ),
        TargetVerificationCheck(
            name="secret_backend",
            ok=secret_backend_ok,
            message=secret_resolution.message,
        ),
        TargetVerificationCheck(
            name="live_cluster",
            ok=live_cluster_ok,
            message=(
                "Live Kubernetes API verification requires an operator read profile"
                if secret_backend_ok
                else "Live Kubernetes API verification requires resolved credentials"
            ),
        ),
    ]

    metadata_ok = endpoint_ok and namespace_ok and secret_ok
    if metadata_ok and secret_backend_ok and not live_cluster_ok:
        return TargetVerification(
            ok=False,
            mode="kubernetes_secret_resolved",
            status="pending",
            message=(
                "Kubernetes target credentials are resolved; live cluster "
                "verification requires an operator read profile"
            ),
            last_error="Kubernetes read profile is not configured",
            checks=checks,
        )
    if metadata_ok and not live_cluster_ok:
        return TargetVerification(
            ok=False,
            mode="kubernetes_metadata",
            status="pending",
            message=(
                "Kubernetes target metadata is complete; live cluster verification "
                "is pending resolvable credentials"
            ),
            last_error="Kubernetes target credentials are not resolved",
            checks=checks,
        )
    return TargetVerification(
        ok=False,
        mode="kubernetes_metadata",
        status="error",
        message="Complete Kubernetes endpoint and secret reference before live verification",
        last_error="Kubernetes target metadata is incomplete",
        checks=checks,
    )


def verify_kubernetes_target(target: Target) -> TargetVerification:
    from fastapi import HTTPException
    from eolgae.config import settings
    from eolgae.services.resource_observation import observe
    if not settings.kubernetes_read_profiles_file:
        return verify_kubernetes_target_metadata(target)
    try:
        result = observe(target)
        checks = [TargetVerificationCheck(name=o["kind"], ok=o["complete"],
                  message=o["message"] or "실제 API 조회 성공") for o in result["outcomes"]]
        ok = result["complete"]
        message = "Kubernetes 실제 조회 성공" if ok else "Kubernetes 조회 범위 또는 연결 오류를 확인하세요."
        return TargetVerification(ok, "kubernetes_live_read", "ready" if ok else "error",
                                  message, None if ok else message, checks)
    except HTTPException as error:
        message = str(error.detail)
        return TargetVerification(False, "kubernetes_live_read", "error", message, message,
                                  [TargetVerificationCheck(name="live_cluster", ok=False, message=message)])
