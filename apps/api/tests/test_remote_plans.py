"""Plan-only boundary, durable intent, deduplication and remote reconciliation."""
import base64
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")
from eolgae.config import settings
from eolgae.integrations import terrakube as tk, terrakube_plan as remote
from eolgae.routers.remote_plans import RequestPlan
from eolgae.services import remote_plans as service


def plan_fixture():
    return SimpleNamespace(id=uuid4(), canvas_id=uuid4(), job_id=None, commit_sha="a" * 40,
        workspace_id=str(uuid4()), organization_id=str(uuid4()), api_url="https://example.test/api/v1",
        status="submitting", result=None, error_message=None, workspace_snapshot={"execution_ref":"review"})


def job_fixture(plan, **overrides):
    return {"id": "42", "attributes": {"comments": remote.marker(plan.id),
        "overrideBranch": plan.workspace_snapshot["execution_ref"], "commitId": plan.commit_sha,
        "tcl": base64.b64encode(remote.PLAN_TCL.encode()).decode(), "status": "completed",
        "planChanges": True, "output": "secret-log", "terraformPlan": "secret-url", **overrides}}


@pytest.mark.parametrize("tcl", [remote.PLAN_TCL.replace("terraformPlan", "terraformApply"),
    remote.PLAN_TCL + '\n  - type: "terraformApply"\n    step: 200',
    remote.PLAN_TCL + '\n    commands: []', remote.PLAN_TCL + '\nimport: untrusted', "bad"])
def test_nonstandard_templates_never_execute(tcl):
    template = str(uuid4())
    with patch.object(settings, "terrakube_plan_template_id", template), patch.object(tk, "_organization", return_value=str(uuid4())), patch.object(tk, "request", return_value={"data": {"id": template, "attributes": {"tcl":base64.b64encode(tcl.encode()).decode()}}}):
        with pytest.raises(HTTPException) as exc: remote.approved_template()
        assert exc.value.status_code == 409


def client_fixture(response=None, error=None):
    client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
    client.post.return_value = response; client.post.side_effect = error
    return client


def test_post_pins_commit_and_inline_plan_without_mutable_template_reference():
    plan = plan_fixture(); client = client_fixture(httpx.Response(201,json={"data":{"id":"42"}}))
    with patch.object(tk,"headers",return_value={}),patch.object(httpx,"Client",return_value=client):
        assert remote.submit(plan) == "42"
    payload = client.post.call_args.kwargs['json']['data']
    assert payload['attributes'] == {'tcl':base64.b64encode(remote.PLAN_TCL.encode()).decode(),
                                    'overrideBranch':'review','commitId':plan.commit_sha,'comments':remote.marker(plan.id)}
    assert payload['relationships']['workspace']['data']['id'] == plan.workspace_id
    assert 'templateReference' not in payload['attributes']
    assert client.post.call_count == 1


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.Response(302), httpx.Response(201,json={"data":{}}), httpx.Response(201,text="bad")])
def test_uncertain_responses_never_retry(response):
    client=client_fixture(response)
    with patch.object(tk,"headers",return_value={}),patch.object(httpx,"Client",return_value=client):
        with pytest.raises(remote.SubmissionUncertain): remote.submit(plan_fixture())
    assert client.post.call_count == 1


def test_timeout_never_retries_or_leaks_error():
    client=client_fixture(error=httpx.ReadTimeout('private-token'))
    with patch.object(tk,"headers",return_value={}),patch.object(httpx,"Client",return_value=client):
        with pytest.raises(remote.SubmissionUncertain) as exc: remote.submit(plan_fixture())
    assert 'private-token' not in str(exc.value)
    assert client.post.call_count == 1


def test_read_scope_does_not_grant_submission():
    user = str(uuid4())
    with patch.multiple(settings,terrakube_enabled=True,terrakube_user_ids=user,terrakube_plan_enabled=True,terrakube_plan_template_id=str(uuid4()),terrakube_plan_user_ids=""):
        assert tk.authorized(user)
        assert not remote.plan_allowed(user)


@pytest.mark.parametrize("change", [{"commitId":"b"*40},{"overrideBranch":"main"},{"comments":"other"},{"tcl":"invalid"}])
def test_reconciliation_checks_immutable_identity(change):
    plan=plan_fixture()
    with pytest.raises(HTTPException) as exc: remote.result_for(plan,job_fixture(plan,**change))
    assert exc.value.status_code == 409


def test_result_excludes_logs_state_urls_and_untyped_change_data():
    plan=plan_fixture()
    status,result=remote.result_for(plan,job_fixture(plan,planChanges={'secret':'no'}))
    assert status=='success' and result['has_changes'] is None
    assert 'secret' not in str(result)


def test_completed_without_commit_stays_unknown():
    plan=plan_fixture()
    assert remote.result_for(plan,job_fixture(plan,commitId=None))[0]=='unknown'


def test_unknown_lookup_matches_correlation_without_resubmitting():
    plan=plan_fixture()
    with patch.object(tk,'workspace_path',return_value='/scoped'),patch.object(tk,'request',return_value={'data':[job_fixture(plan),{'id':'1','attributes':{'comments':'another'}}]}),patch.object(remote,'submit') as send:
        assert remote.lookup(plan)['id']=='42'
        send.assert_not_called()


def request_fixture(canvas):
    return RequestPlan(idempotency_key=uuid4(),commit_sha='a'*40,canvas_revision=service.canvas_revision(canvas))


def canvas_fixture():
    return SimpleNamespace(id=uuid4(),graph={'nodes':[]},schema_version='0.1.0',canvas_kind='aws',
                           execution_backend='terrakube',terrakube_workspace_id=str(uuid4()))


def test_idempotent_repeat_returns_original_without_submit():
    canvas=canvas_fixture();body=request_fixture(canvas);db=Mock()
    existing=SimpleNamespace(commit_sha=body.commit_sha,canvas_revision=body.canvas_revision)
    db.scalar.return_value=existing
    with patch.object(service,'require_binding'),patch.object(remote,'submit') as send:
        assert service.create_plan(db,canvas,uuid4(),body) is existing
        send.assert_not_called();db.commit.assert_not_called()


@pytest.mark.parametrize('case',['reused_key','stale','active'])
def test_conflicting_requests_do_not_reach_remote(case):
    canvas=canvas_fixture();body=request_fixture(canvas);db=Mock()
    if case=='reused_key':db.scalar.return_value=SimpleNamespace(commit_sha='b'*40,canvas_revision=body.canvas_revision)
    elif case=='stale':
        db.scalar.return_value=None;canvas.graph={'nodes':[{'id':'new'}]}
    else:db.scalar.side_effect=[None,uuid4()]
    with patch.object(service,'require_binding'),patch.object(remote,'submit') as send,patch.object(remote,'approved_template') as template:
        with pytest.raises(HTTPException) as exc:service.create_plan(db,canvas,uuid4(),body)
        assert exc.value.status_code==409
        send.assert_not_called();template.assert_not_called()


def test_intent_committed_before_post_and_timeout_persisted():
    canvas=canvas_fixture();body=request_fixture(canvas);db=Mock();db.scalar.side_effect=[None,None,None]
    def uncertain(plan):
        assert db.commit.call_count==1
        assert plan.id is not None and plan.status=='submitting'
        raise remote.SubmissionUncertain()
    with patch.object(service,'require_binding'),patch.object(remote,'approved_template',return_value=str(uuid4())),patch.object(tk,'get_workspace',return_value={'branch':'review'}),patch.object(tk,'_organization',return_value=str(uuid4())),patch.object(settings,'terrakube_api_url','https://example.test/api/v1'),patch.object(remote,'submit',side_effect=uncertain):
        plan=service.create_plan(db,canvas,uuid4(),body)
    assert plan.status=='unknown' and db.commit.call_count==2


def test_reconciliation_error_preserves_active_request():
    plan=plan_fixture();plan.status='pending';plan.job_id='42';db=Mock()
    with patch.object(service,'require_identity'),patch.object(remote,'lookup',side_effect=HTTPException(504,'timeout')):
        service.reconcile(db,plan,uuid4())
    assert plan.status=='pending' and plan.job_id=='42'


@pytest.mark.parametrize('change',[{'commit_sha':'main'},{'template_id':str(uuid4())},{'operation':'apply'}])
def test_request_rejects_branch_and_caller_supplied_execution_options(change):
    body=dict(idempotency_key=uuid4(),commit_sha='a'*40,canvas_revision='b'*64,**{})
    body.update(change)
    with pytest.raises(ValidationError):RequestPlan(**body)
