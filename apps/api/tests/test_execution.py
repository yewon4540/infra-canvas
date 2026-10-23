"""Regression tests for the boundary between observation and execution."""
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")

from eolgae.config import settings
from eolgae.execution.policy import require_direct_execution
from eolgae.execution.dispatch import run_plan
from eolgae.integrations import terrakube
from eolgae.routers import execution
from eolgae.routers.deployment_routes import plans, approval, apply, destroy
from eolgae.routers.canvas import plan_canvas


@pytest.mark.parametrize("backend,enabled", [("eolgae_direct", False), ("terrakube", True), ("terrakube", False)])
def test_no_direct_execution_without_both_capability_and_ownership(backend, enabled):
    with patch.object(settings, "direct_execution_enabled", enabled):
        with pytest.raises(HTTPException) as exc:
            require_direct_execution(SimpleNamespace(execution_backend=backend))
        assert exc.value.status_code == 409


@pytest.mark.parametrize("call", [plans.create_plan_deployment, plans.create_destroy_plan_deployment,
                                  approval.approve_plan_deployment, apply.create_apply_deployment,
                                  destroy.create_destroy_deployment])
def test_routes_reject_before_db_mutation_or_queuing(call):
    user = SimpleNamespace(id=uuid4())
    canvas = SimpleNamespace(id=uuid4(), owner_id=user.id, deleted_at=None, execution_backend="terrakube")
    db = Mock(); db.get.return_value = canvas
    kwargs = dict(canvas_id=canvas.id, user=user, db=db)
    if call not in (plans.create_plan_deployment, plans.create_destroy_plan_deployment):
        kwargs['deployment_id'] = uuid4()
    with patch.object(settings, "direct_execution_enabled", True), patch.object(run_plan, "send") as send:
        with pytest.raises(HTTPException) as exc:
            call(**kwargs)
        assert exc.value.status_code == 409
        db.add.assert_not_called(); db.commit.assert_not_called(); send.assert_not_called()


def test_legacy_sync_plan_is_retired():
    user = SimpleNamespace(id=uuid4())
    db = Mock(); db.get.return_value = SimpleNamespace(owner_id=user.id, deleted_at=None)
    with pytest.raises(HTTPException) as exc:
        plan_canvas(uuid4(), user=user, db=db)
    assert exc.value.status_code == 410


def test_binding_cannot_move_existing_state():
    user = SimpleNamespace(id=uuid4()); workspace = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(id=uuid4(), owner_id=user.id, deleted_at=None,
                                        execution_backend="eolgae_direct")
    db.scalar.return_value = uuid4()
    with patch.object(terrakube, "require_access"), patch.object(terrakube, "get_workspace") as remote:
        with pytest.raises(HTTPException) as exc:
            execution.bind_terrakube(uuid4(), execution.BindTerrakube(workspace_id=workspace), user, db)
        assert exc.value.status_code == 409
        remote.assert_not_called(); db.commit.assert_not_called()


def test_remote_access_requires_user_and_workspace_allowlists():
    user, workspace = str(uuid4()), str(uuid4())
    with patch.multiple(settings, terrakube_enabled=True, terrakube_user_ids=user,
                        terrakube_workspace_ids=workspace):
        terrakube.require_access(user, workspace)
        for uid, wid in [(str(uuid4()), workspace), (user, str(uuid4()))]:
            with pytest.raises(HTTPException) as exc:
                terrakube.require_access(uid, wid)
            assert exc.value.status_code == 403


@pytest.mark.parametrize("status,expected", [(401, 502), (403, 502), (404, 404), (302, 502), (500, 502)])
def test_remote_errors_do_not_leak_upstream_body_or_token(tmp_path, status, expected):
    secret = tmp_path / 'token'; secret.write_text('private-test-token')
    response = httpx.Response(status, json={"secret": "private-test-token"})
    client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
    client.get.return_value = response
    with patch.multiple(settings, terrakube_enabled=True, terrakube_api_url="https://example.test/api/v1",
                        terrakube_organization_id=str(uuid4()), terrakube_token_file=str(secret),
                        terrakube_workspace_ids=str(uuid4())), patch.object(httpx, "Client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            terrakube.request('/organization/test')
        assert exc.value.status_code == expected
        assert 'private-test-token' not in str(exc.value.detail)


def test_jobs_expose_only_summary_and_do_not_follow_pagination_url():
    workspace = str(uuid4())
    with patch.object(terrakube, "request", return_value={"data": [
        {"id": "2", "attributes": {"status": "waitingApproval", "output": "secret", "variables": "secret"}}
    ], "links": {"next": "https://untrusted.invalid/"}}) as remote, patch.object(terrakube, "_organization", return_value=str(uuid4())):
        result = terrakube.get_jobs(workspace)
        assert result['has_more'] is True
        assert result['items'][0]['status'] == 'waitingApproval'
        assert 'secret' not in str(result)
        assert remote.call_count == 1


def test_timeout_is_distinct_from_empty_result(tmp_path):
    secret = tmp_path / 'token'; secret.write_text('test-token')
    client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
    client.get.side_effect = httpx.ReadTimeout('private upstream URL')
    with patch.multiple(settings, terrakube_enabled=True, terrakube_api_url="https://example.test/api/v1",
                        terrakube_organization_id=str(uuid4()), terrakube_token_file=str(secret),
                        terrakube_workspace_ids=str(uuid4())), patch.object(httpx, "Client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            terrakube.request('/organization/test')
        assert exc.value.status_code == 504
        assert 'private upstream' not in str(exc.value.detail)
