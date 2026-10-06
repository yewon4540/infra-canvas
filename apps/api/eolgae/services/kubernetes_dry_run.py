"""Kubernetes dry-run readiness boundary.

This module does not execute kubectl yet. It combines local manifest validation
with target credential resolution so the API can report why cluster-side dry-run
is unavailable without leaking credential material.
"""
from __future__ import annotations

from typing import Any

from eolgae.models.target import Target
from eolgae.services.target_secrets import resolve_kubernetes_credentials


def kubernetes_dry_run_status(
    *,
    validation_result: dict[str, Any],
    target: Target | None,
) -> dict[str, Any]:
    if not validation_result.get("ok"):
        return {
            "mode": "local_validation_failed",
            "ready": False,
            "blocked_by": "local_validation",
            "message": "Cluster-side dry-run은 local manifest validation 통과 후 실행할 수 있습니다.",
        }

    if target is None:
        return {
            "mode": "not_configured",
            "ready": False,
            "blocked_by": "target",
            "message": "Cluster-side dry-run은 Kubernetes Target 연결 후 활성화됩니다.",
        }

    resolution = resolve_kubernetes_credentials(
        endpoint=target.endpoint,
        config=target.config,
        secret_ref=target.secret_ref,
    )
    if not resolution.ok:
        return {
            "mode": "credentials_pending",
            "ready": False,
            "blocked_by": "credentials",
            "target_id": str(target.id),
            "message": resolution.message,
        }

    return {
        "mode": "credentials_resolved",
        "ready": False,
        "blocked_by": "kubernetes_client_adapter",
        "target_id": str(target.id),
        "namespace": resolution.credentials.default_namespace
        if resolution.credentials
        else "default",
        "message": (
            "Kubernetes credentials are resolved. Actual server-side dry-run "
            "will run after the Kubernetes client adapter is added."
        ),
    }
