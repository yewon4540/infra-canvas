"""Secret reference resolution for provider targets.

Resolvers return credential material to in-process callers only. Target rows keep
references such as environment variable names, not token or certificate values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KubernetesCredentials:
    endpoint: str
    token: str
    ca_cert: str
    default_namespace: str


@dataclass(frozen=True)
class SecretResolution:
    ok: bool
    backend: str
    message: str
    credentials: KubernetesCredentials | None = None


def resolve_kubernetes_credentials(
    *,
    endpoint: str | None,
    config: dict[str, Any] | None,
    secret_ref: dict[str, Any] | None,
) -> SecretResolution:
    """Resolve Kubernetes credentials from a target secret reference.

    Supported MVP2-prep backend:
    - `backend: "env"` with `token_env` and `ca_cert_env`

    The legacy shape with only `name` remains valid metadata, but it is not
    resolvable until a real secret store adapter is added.
    """

    if not secret_ref:
        return SecretResolution(
            ok=False,
            backend="missing",
            message="Secret reference is required before live verification",
        )

    backend = _backend(secret_ref)
    if backend != "env":
        return SecretResolution(
            ok=False,
            backend=backend,
            message=f"Secret backend '{backend}' is not configured",
        )

    token_env = _clean(secret_ref.get("token_env"))
    ca_cert_env = _clean(secret_ref.get("ca_cert_env"))
    endpoint_env = _clean(secret_ref.get("endpoint_env"))

    missing_refs = [
        label
        for label, value in (
            ("token_env", token_env),
            ("ca_cert_env", ca_cert_env),
        )
        if not value
    ]
    if missing_refs:
        return SecretResolution(
            ok=False,
            backend=backend,
            message=f"Env secret reference is missing {', '.join(missing_refs)}",
        )

    resolved_endpoint = _clean(os.environ.get(endpoint_env)) if endpoint_env else endpoint
    token = _clean(os.environ.get(token_env or ""))
    ca_cert = _clean(os.environ.get(ca_cert_env or ""))
    missing_values = [
        label
        for label, value in (
            ("endpoint", resolved_endpoint),
            ("token", token),
            ("ca_cert", ca_cert),
        )
        if not value
    ]
    if missing_values:
        return SecretResolution(
            ok=False,
            backend=backend,
            message=f"Env secret values are missing {', '.join(missing_values)}",
        )

    return SecretResolution(
        ok=True,
        backend=backend,
        message="Kubernetes credentials resolved from env secret reference",
        credentials=KubernetesCredentials(
            endpoint=resolved_endpoint or "",
            token=token or "",
            ca_cert=ca_cert or "",
            default_namespace=_default_namespace(config),
        ),
    )


def _backend(secret_ref: dict[str, Any]) -> str:
    return _clean(secret_ref.get("backend") or secret_ref.get("type")) or "unconfigured"


def _default_namespace(config: dict[str, Any] | None) -> str:
    value = _clean((config or {}).get("default_namespace"))
    return value or "default"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
