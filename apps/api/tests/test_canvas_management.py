from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

db_module = types.ModuleType("eolgae.db")
db_module.get_db = Mock()
db_module.SessionLocal = Mock()
sys.modules.setdefault("eolgae.db", db_module)

auth_dependencies = types.ModuleType("eolgae.auth.dependencies")
auth_dependencies.get_current_user = Mock()
sys.modules.setdefault("eolgae.auth.dependencies", auth_dependencies)

from eolgae.routers import canvas as canvas_router
from eolgae.pipelines.validation import validate_canvas_for_plan
from eolgae.schemas.canvas import (
    CanvasDuplicateRequest,
    CanvasFromTemplateRequest,
    CanvasInsertFragmentRequest,
)


def test_duplicate_canvas_resets_state_and_strips_aws_binding() -> None:
    user_id = uuid4()
    canvas_id = uuid4()
    connection_id = uuid4()
    environment_id = uuid4()
    source = SimpleNamespace(
        id=canvas_id,
        name="Applied S3",
        description="source",
        schema_version="0.1.0",
        state="applied",
        canvas_kind="kubernetes",
        graph={
            "nodes": [
                {
                    "id": "node_s3",
                    "type": "aws.s3.bucket",
                    "display_name": "bucket",
                    "position": {"x": 0, "y": 0},
                    "properties": {"bucket_name": "existing"},
                    "metadata": {},
                    "aws_binding": {"arn": "arn:aws:s3:::existing"},
                }
            ],
            "edges": [],
            "groups": [],
        },
        aws_connection_id=connection_id,
        aws_account={"account_id": "123456789012"},
        owner_id=user_id,
        group_id=uuid4(),
        environment_id=environment_id,
        deleted_at=None,
    )
    user = SimpleNamespace(id=user_id)
    db = Mock()
    db.get.return_value = source
    db.refresh.side_effect = lambda created: setattr(created, "id", uuid4())

    created = canvas_router.duplicate_canvas(
        canvas_id=canvas_id,
        payload=CanvasDuplicateRequest(),
        user=user,
        db=db,
    )

    assert created.name == "Applied S3 Copy"
    assert created.state == "design"
    assert created.canvas_kind == "kubernetes"
    assert created.aws_connection_id == connection_id
    assert created.environment_id == environment_id
    assert "aws_binding" not in created.graph["nodes"][0]
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_canvas_from_template_creates_design_canvas() -> None:
    user = SimpleNamespace(id=uuid4())
    db = Mock()
    db.refresh.side_effect = lambda created: setattr(created, "id", uuid4())

    created = canvas_router.create_canvas_from_template(
        payload=CanvasFromTemplateRequest(template_id="s3-private-bucket"),
        user=user,
        db=db,
    )

    assert created.name == "정적 파일 호스팅"
    assert created.state == "design"
    assert created.canvas_kind == "aws"
    assert created.owner_id == user.id
    assert created.graph["nodes"][0]["type"] == "aws.s3.bucket"
    assert created.graph["nodes"][0]["properties"]["public_access_block"] is True
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_canvas_accepts_kubernetes_kind() -> None:
    user = SimpleNamespace(id=uuid4())
    db = Mock()
    db.refresh.side_effect = lambda created: setattr(created, "id", uuid4())

    created = canvas_router.create_canvas(
        payload=canvas_router.CanvasCreate(
            name="Kubernetes Workloads",
            canvas_kind="kubernetes",
        ),
        user=user,
        db=db,
    )

    assert created.canvas_kind == "kubernetes"
    assert created.aws_connection_id is None
    assert created.aws_account is None
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_kubernetes_canvas_binds_kubernetes_target() -> None:
    user = SimpleNamespace(id=uuid4())
    target_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        id=target_id,
        owner_id=user.id,
        kind="kubernetes_cluster",
        deleted_at=None,
        archived_at=None,
    )
    db.refresh.side_effect = lambda created: setattr(created, "id", uuid4())

    created = canvas_router.create_canvas(
        payload=canvas_router.CanvasCreate(
            name="Kubernetes Workloads",
            canvas_kind="kubernetes",
            aws_connection_id=uuid4(),
            target_id=target_id,
        ),
        user=user,
        db=db,
    )

    assert created.canvas_kind == "kubernetes"
    assert created.target_id == target_id
    assert created.aws_connection_id is None
    assert created.aws_account is None
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_kubernetes_canvas_rejects_non_kubernetes_target() -> None:
    user = SimpleNamespace(id=uuid4())
    target_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        id=target_id,
        owner_id=user.id,
        kind="aws_account",
        deleted_at=None,
        archived_at=None,
    )

    with pytest.raises(canvas_router.HTTPException) as exc:
        canvas_router.create_canvas(
            payload=canvas_router.CanvasCreate(
                name="Kubernetes Workloads",
                canvas_kind="kubernetes",
                target_id=target_id,
            ),
            user=user,
            db=db,
        )

    assert exc.value.status_code == 400
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_kubernetes_canvas_rejects_unavailable_target() -> None:
    user = SimpleNamespace(id=uuid4())
    target_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(
        id=target_id,
        owner_id=uuid4(),
        kind="kubernetes_cluster",
        deleted_at=None,
        archived_at=None,
    )

    with pytest.raises(canvas_router.HTTPException) as exc:
        canvas_router.create_canvas(
            payload=canvas_router.CanvasCreate(
                name="Kubernetes Workloads",
                canvas_kind="kubernetes",
                target_id=target_id,
            ),
            user=user,
            db=db,
        )

    assert exc.value.status_code == 403
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_list_canvas_templates_exposes_builtin_templates() -> None:
    templates = canvas_router.list_canvas_templates(user=SimpleNamespace(id=uuid4()))
    template_ids = {template.id for template in templates}

    assert "s3-private-bucket" in template_ids
    assert "web-alb-ec2-rds" in template_ids
    assert "vpc-two-subnets" not in template_ids


def test_generate_kubernetes_yaml_for_canvas_returns_manifest() -> None:
    user_id = uuid4()
    canvas_id = uuid4()
    canvas = SimpleNamespace(
        id=canvas_id,
        name="K8S App",
        graph={
            "nodes": [
                {
                    "id": "web",
                    "type": "kubernetes.deployment",
                    "display_name": "web-api",
                    "properties": {
                        "namespace": "platform",
                        "image": "nginx:1.27",
                    },
                }
            ],
            "edges": [],
            "groups": [],
        },
        owner_id=user_id,
        deleted_at=None,
    )
    db = Mock()
    db.get.return_value = canvas

    result = canvas_router.generate_kubernetes_yaml_for_canvas(
        canvas_id=canvas_id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result["filename"] == "K8S_App.k8s.yaml"
    assert "kind: Deployment" in result["yaml"]
    assert "namespace: platform" in result["yaml"]


def test_validate_kubernetes_canvas_returns_manifest_issues() -> None:
    user_id = uuid4()
    canvas_id = uuid4()
    canvas = SimpleNamespace(
        id=canvas_id,
        name="K8S App",
        canvas_kind="kubernetes",
        target_id=None,
        graph={
            "nodes": [
                {
                    "id": "web",
                    "type": "kubernetes.deployment",
                    "display_name": "web",
                    "properties": {"namespace": "platform", "image": "nginx:1.27"},
                },
                {
                    "id": "ing",
                    "type": "kubernetes.ingress",
                    "display_name": "web-ingress",
                    "properties": {
                        "namespace": "platform",
                        "service_name": "missing-service",
                    },
                },
            ],
            "edges": [],
            "groups": [],
        },
        owner_id=user_id,
        deleted_at=None,
    )
    db = Mock()
    db.get.return_value = canvas

    result = canvas_router.validate_kubernetes_for_canvas(
        canvas_id=canvas_id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result["ok"] is False
    assert result["summary"]["errors"] == 1
    assert result["dry_run"]["mode"] == "local_validation_failed"
    assert result["dry_run"]["blocked_by"] == "local_validation"
    assert "kind: Deployment" in result["yaml"]
    assert any(
        issue["code"] == "ingress_service_missing"
        for issue in result["issues"]
    )


def test_validate_kubernetes_canvas_reports_resolved_dry_run_credentials(monkeypatch) -> None:
    monkeypatch.setenv("EOLGAE_TEST_KUBE_TOKEN", "test-token")
    monkeypatch.setenv("EOLGAE_TEST_KUBE_CA", "test-ca")
    user_id = uuid4()
    canvas_id = uuid4()
    target_id = uuid4()
    canvas = SimpleNamespace(
        id=canvas_id,
        name="K8S App",
        canvas_kind="kubernetes",
        target_id=target_id,
        graph={
            "nodes": [
                {
                    "id": "web",
                    "type": "kubernetes.deployment",
                    "display_name": "web",
                    "properties": {
                        "namespace": "platform",
                        "name": "web",
                        "image": "nginx:1.27",
                    },
                },
                {
                    "id": "svc",
                    "type": "kubernetes.service",
                    "display_name": "web",
                    "properties": {
                        "namespace": "platform",
                        "name": "web",
                        "selector": "web",
                    },
                },
            ],
            "edges": [],
            "groups": [],
        },
        owner_id=user_id,
        deleted_at=None,
    )
    target = SimpleNamespace(
        id=target_id,
        owner_id=user_id,
        kind="kubernetes_cluster",
        endpoint="https://kubernetes.example.com:6443",
        config={"default_namespace": "platform"},
        secret_ref={
            "backend": "env",
            "name": "cluster-reader",
            "token_env": "EOLGAE_TEST_KUBE_TOKEN",
            "ca_cert_env": "EOLGAE_TEST_KUBE_CA",
        },
        deleted_at=None,
        archived_at=None,
    )
    db = Mock()
    db.get.side_effect = [canvas, target]

    result = canvas_router.validate_kubernetes_for_canvas(
        canvas_id=canvas_id,
        user=SimpleNamespace(id=user_id),
        db=db,
    )

    assert result["ok"] is True
    assert result["target_id"] == str(target_id)
    assert result["dry_run"]["mode"] == "credentials_resolved"
    assert result["dry_run"]["ready"] is False
    assert result["dry_run"]["blocked_by"] == "kubernetes_client_adapter"
    assert result["dry_run"]["namespace"] == "platform"
    assert "test-token" not in result["dry_run"]["message"]


def test_validate_kubernetes_rejects_aws_canvas() -> None:
    user_id = uuid4()
    canvas_id = uuid4()
    canvas = SimpleNamespace(
        id=canvas_id,
        name="AWS App",
        canvas_kind="aws",
        graph={"nodes": [], "edges": [], "groups": []},
        owner_id=user_id,
        deleted_at=None,
    )
    db = Mock()
    db.get.return_value = canvas

    with pytest.raises(canvas_router.HTTPException) as exc:
        canvas_router.validate_kubernetes_for_canvas(
            canvas_id=canvas_id,
            user=SimpleNamespace(id=user_id),
            db=db,
        )

    assert exc.value.status_code == 400


def test_builtin_templates_are_plan_validation_ready() -> None:
    templates = canvas_router._template_graphs()

    for template_id, template in templates.items():
        issues = validate_canvas_for_plan(
            {
                "graph": template["graph"],
                "aws_account": {"default_region": "ap-northeast-2"},
            }
        )

        assert issues == [], template_id


def test_list_canvas_fragments_exposes_vpc_basic_2az() -> None:
    fragments = canvas_router.list_canvas_fragments(user=SimpleNamespace(id=uuid4()))
    fragment_ids = {fragment.id for fragment in fragments}

    assert "vpc-basic-2az" in fragment_ids


def test_insert_canvas_fragment_prefixes_ids_and_offsets_positions() -> None:
    user_id = uuid4()
    canvas_id = uuid4()
    source = SimpleNamespace(
        id=canvas_id,
        name="Network",
        description=None,
        schema_version="0.1.0",
        state="applied",
        graph={
            "nodes": [
                {
                    "id": "existing_vpc",
                    "type": "aws.ec2.vpc",
                    "display_name": "existing",
                    "position": {"x": 10, "y": 20},
                    "properties": {"cidr": "10.0.0.0/16"},
                    "metadata": {},
                }
            ],
            "edges": [],
            "groups": [],
        },
        aws_connection_id=None,
        aws_account=None,
        owner_id=user_id,
        group_id=None,
        environment_id=None,
        deleted_at=None,
    )
    user = SimpleNamespace(id=user_id)
    db = Mock()
    db.get.return_value = source

    updated = canvas_router.insert_canvas_fragment(
        canvas_id=canvas_id,
        payload=CanvasInsertFragmentRequest(fragment_id="vpc-basic-2az", x=200, y=300),
        user=user,
        db=db,
    )

    assert updated.state == "design"
    assert len(updated.graph["nodes"]) == 8
    assert len(updated.graph["edges"]) == 4
    inserted_nodes = [node for node in updated.graph["nodes"] if node["id"] != "existing_vpc"]
    assert all(node["id"].startswith("frag_") for node in inserted_nodes)
    inserted_vpc = next(node for node in inserted_nodes if node["display_name"] == "main-vpc")
    assert inserted_vpc["position"] == {"x": 200.0, "y": 300.0}
    public_a = next(node for node in inserted_nodes if node["display_name"] == "public-a")
    assert public_a["parent_group_id"] == inserted_vpc["id"]
    assert public_a["position"] == {"x": 260.0, "y": 410.0}
    assert validate_canvas_for_plan({"graph": updated.graph, "aws_account": {}}) == []
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(source)
