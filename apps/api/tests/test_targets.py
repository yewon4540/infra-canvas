from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

db_module = types.ModuleType("eolgae.db")
db_module.get_db = Mock()
db_module.SessionLocal = Mock()
sys.modules.setdefault("eolgae.db", db_module)

auth_dependencies = types.ModuleType("eolgae.auth.dependencies")
auth_dependencies.get_current_user = Mock()
sys.modules.setdefault("eolgae.auth.dependencies", auth_dependencies)

from eolgae.routers import targets as targets_router


def test_verify_kubernetes_target_stays_pending_until_live_check() -> None:
    user_id = uuid4()
    target = SimpleNamespace(
        id=uuid4(),
        owner_id=user_id,
        deleted_at=None,
        kind="kubernetes_cluster",
        endpoint="https://kubernetes.example.com:6443",
        config={"default_namespace": "platform"},
        secret_ref={"type": "kubeconfig", "name": "cluster-kubeconfig"},
        status="pending",
        last_error=None,
        last_verified_at=None,
    )
    db = Mock()
    db.get.return_value = target
    db.refresh.side_effect = lambda item: item

    result = targets_router.verify_target(
        target_id=target.id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result.ok is False
    assert result.mode == "kubernetes_metadata"
    assert result.status == "pending"
    assert target.status == "pending"
    assert target.last_error == "Kubernetes target credentials are not resolved"
    assert any(check.name == "secret_backend" and not check.ok for check in result.checks)
    assert any(check.name == "live_cluster" and not check.ok for check in result.checks)
    db.commit.assert_called_once()


def test_verify_kubernetes_target_resolves_env_secret_ref(monkeypatch) -> None:
    monkeypatch.setenv("EOLGAE_TEST_KUBE_TOKEN", "test-token")
    monkeypatch.setenv("EOLGAE_TEST_KUBE_CA", "test-ca")
    user_id = uuid4()
    target = SimpleNamespace(
        id=uuid4(),
        owner_id=user_id,
        deleted_at=None,
        kind="kubernetes_cluster",
        endpoint="https://kubernetes.example.com:6443",
        config={"default_namespace": "platform"},
        secret_ref={
            "backend": "env",
            "type": "service_account",
            "name": "cluster-reader",
            "token_env": "EOLGAE_TEST_KUBE_TOKEN",
            "ca_cert_env": "EOLGAE_TEST_KUBE_CA",
        },
        status="pending",
        last_error=None,
        last_verified_at=None,
    )
    db = Mock()
    db.get.return_value = target
    db.refresh.side_effect = lambda item: item

    result = targets_router.verify_target(
        target_id=target.id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result.ok is False
    assert result.mode == "kubernetes_secret_resolved"
    assert result.status == "pending"
    assert target.status == "pending"
    assert target.last_error == "Kubernetes read profile is not configured"
    assert any(check.name == "secret_backend" and check.ok for check in result.checks)
    assert all("test-token" not in check.message for check in result.checks)


def test_kubernetes_read_only_manifest_uses_minimum_read_verbs() -> None:
    result = targets_router.get_kubernetes_read_only_manifest(
        namespace="Eolgae System",
        service_account_name="Eolgae Reader",
        cluster_role_name="Eolgae ReadOnly",
        cluster_role_binding_name="Eolgae Reader",
        user=SimpleNamespace(id=uuid4()),
    )

    assert result.namespace == "eolgae-system"
    assert result.service_account_name == "eolgae-reader"
    assert "kind: ServiceAccount" in result.manifest
    assert "kind: ClusterRole" in result.manifest
    assert 'verbs: ["get", "list", "watch"]' in result.manifest
    assert "create" not in result.manifest
    assert "update" not in result.manifest
    assert "delete" not in result.manifest
    assert "kubectl -n eolgae-system create token eolgae-reader" in result.token_command


def test_verify_kubernetes_target_requires_secret_ref() -> None:
    user_id = uuid4()
    target = SimpleNamespace(
        id=uuid4(),
        owner_id=user_id,
        deleted_at=None,
        kind="kubernetes_cluster",
        endpoint="https://kubernetes.example.com:6443",
        config={"default_namespace": "default"},
        secret_ref=None,
        status="pending",
        last_error=None,
        last_verified_at=None,
    )
    db = Mock()
    db.get.return_value = target
    db.refresh.side_effect = lambda item: item

    result = targets_router.verify_target(
        target_id=target.id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result.ok is False
    assert result.status == "error"
    assert target.status == "error"
    assert target.last_error == "Kubernetes target metadata is incomplete"
    assert any(check.name == "secret_ref" and not check.ok for check in result.checks)


def test_verify_aws_target_reuses_connection_state() -> None:
    user_id = uuid4()
    connection_id = uuid4()
    target = SimpleNamespace(
        id=uuid4(),
        owner_id=user_id,
        deleted_at=None,
        kind="aws_account",
        aws_connection_id=connection_id,
        status="draft",
        last_error=None,
        last_verified_at=None,
    )
    connection = SimpleNamespace(
        id=connection_id,
        owner_id=user_id,
        binding_status="verified",
    )
    db = Mock()
    db.get.side_effect = [target, connection]
    db.refresh.side_effect = lambda item: item

    result = targets_router.verify_target(
        target_id=target.id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result.ok is True
    assert result.mode == "aws_connection"
    assert target.status == "ready"
