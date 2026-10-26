"""Evidence, isolation and incomplete-collection regression cases."""
import os
os.environ.setdefault('DATABASE_URL', 'postgresql+psycopg://test:test@localhost/test')
os.environ.setdefault('JWT_SECRET', 'test-secret')
import json
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from eolgae.services.resources import snapshots, access, analysis, execution
from eolgae.integrations.kubernetes import signals
from eolgae.integrations.aws_inventory import reader, normalize
from eolgae.config import settings


def item(uid='pod', restarts='0'):
    return {'uid': uid, 'kind': 'Pod', 'name': 'example', 'namespace': 'demo', 'status': 'Running',
            'summary': {'restarts': restarts}, 'observed_at': '2026-10-26T00:00:00+00:00', 'management': '미확인'}


def observation(items=None, complete=True):
    return {'observed_at': '2026-10-26T00:00:00+00:00', 'items': [item()] if items is None else items,
            'outcomes': [{'kind': 'Pod', 'complete': complete, 'status': 'success' if complete else 'error'}],
            'relations': [], 'complete': complete, 'signals': [], 'signal_outcome': {'status': 'success'}}


@pytest.mark.parametrize('status', ['error', 'incomplete'])
def test_incomplete_does_not_delete_or_freshen_previous(status):
    old = snapshots.compare_and_merge(observation())
    current = observation([], False); current['outcomes'][0]['status'] = status
    current['observed_at'] = '2026-10-26T00:10:00+00:00'
    result = snapshots.compare_and_merge(current, old)
    assert result['items'][0]['observed_at'] == old['items'][0]['observed_at']
    assert not result['changes']
    assert result['last_success_at'] == old['observed_at']


def test_complete_absence_deletes_and_restart_delta_is_evidence():
    old = snapshots.compare_and_merge(observation())
    assert snapshots.compare_and_merge(observation([]), old)['changes'][0]['type'] == 'removed'
    new = snapshots.compare_and_merge(observation([item(restarts='3')]), old)
    assert new['changes'][0]['before']['summary']['restarts'] == '0'
    assert new['changes'][0]['after']['summary']['restarts'] == '3'
    assert new['signals'][0]['count'] == 3


def test_new_uid_is_not_same_resource_by_name():
    result = snapshots.compare_and_merge(observation([item('new')]), observation())
    assert {c['type'] for c in result['changes']} == {'added', 'removed'}


def test_partial_retention_bounded():
    old = observation([item(str(i)) for i in range(1000)])
    current = observation([item('new')], False)
    result = snapshots.compare_and_merge(current, old)
    assert len(result['items']) == 1000 and result['items'][0]['uid'] == 'new'


def target():
    return NS(id=uuid4(), owner_id=uuid4(), kind='kubernetes_cluster', endpoint='https://cluster.example',
              secret_ref={'name':'reader'}, aws_connection_id=None, archived_at=None, deleted_at=None)


def test_saved_access_rechecks_scope_and_identity(monkeypatch):
    t = target(); monkeypatch.setattr(access, 'scope_for', lambda _: {'namespaces':['demo'],'default_namespace':'demo'})
    _, first = access.authorize_scope(Mock(), t, 'demo')
    with pytest.raises(HTTPException): access.authorize_scope(Mock(), t, '*')
    t.endpoint = 'https://different.example'
    assert access.authorize_scope(Mock(), t, 'demo')[1] != first
    t.archived_at = 'now'
    with pytest.raises(HTTPException): access.authorize_scope(Mock(), t, 'demo')


def test_aws_connection_must_be_owned_verified():
    t = target(); t.aws_connection_id = uuid4(); db=Mock()
    db.get.return_value = NS(owner_id=uuid4(), binding_status='verified')
    with pytest.raises(HTTPException): access.connection_for(db,t)


def test_cannot_bind_other_target_or_owner_canvas():
    db=Mock();db.scalar.return_value=None
    with pytest.raises(HTTPException) as e: execution.bind(db,target(),NS(id=uuid4()),'key','uid',uuid4())
    assert e.value.status_code==403
    db.add.assert_not_called()


def test_saved_snapshot_id_cannot_cross_scope():
    db=Mock();db.scalar.return_value=None
    with pytest.raises(HTTPException) as e: snapshots.get_snapshot(db,target(),'allowed-key',uuid4())
    assert e.value.status_code==404
    query=str(db.scalar.call_args.args[0])
    assert 'scope_key' in query and 'target_id' in query


def test_signals_exclude_event_messages_and_other_uid(monkeypatch):
    fake=MagicMock();fake.__enter__.return_value=fake
    fake.collect.return_value=([
        {'metadata':{'uid':'event'}, 'involvedObject':{'uid':'pod','namespace':'demo'},'reason':'BackOff',
         'type':'Warning','message':'PRIVATE TOKEN','count':3},
        {'involvedObject':{'uid':'other','namespace':'demo'},'message':'PRIVATE'}],True)
    monkeypatch.setattr(signals,'Reader',lambda _:fake)
    events,outcome=signals.event_signals(None,[item()],'now')
    assert outcome['status']=='success' and len(events)==1
    assert 'PRIVATE' not in json.dumps(events)


def test_workload_signals_only_allow_reason_codes():
    raw=[('Pod',{'metadata':{'uid':'pod'},'status':{'containerStatuses':[{'state':{'waiting':{'reason':'CrashLoopBackOff','message':'secret'}}}]}})]
    result=signals.workload_signals(raw,'now')
    assert result[0]['reason']=='CrashLoopBackOff' and 'secret' not in json.dumps(result)


def test_aws_normalizes_only_allowed_fields_and_relationships():
    connection=NS(account_id='123456789012',default_region='ap-northeast-2')
    items,edges=normalize.normalize('EC2',[{'InstanceId':'i-1','VpcId':'vpc-1','SubnetId':'subnet-1',
        'SecurityGroups':[{'GroupId':'sg-1'}],'Tags':[{'Key':'secret','Value':'PRIVATE'}],
        'UserData':'PRIVATE','State':{'Name':'running'}}],connection,'now')
    assert len(edges)==3 and 'PRIVATE' not in json.dumps(items)
    assert items[0]['uid'].startswith('aws:123456789012:ap-northeast-2:')


def test_aws_pagination_bounded_and_read_only():
    client=Mock();client.describe_instances.return_value={'Reservations':[{'Instances':[{'InstanceId':'i-1'}]}],'NextToken':'next'}
    items,complete=reader.collect(client,'describe_instances','Reservations',float('inf'))
    assert not complete and len(items)==5 and client.describe_instances.call_count==5
    assert client.describe_instances.call_args.kwargs['NextToken']=='next'
    assert all(a.startswith('ec2:Describe') for a in json.loads(reader.POLICY)['Statement'][0]['Action'])


def test_aws_assume_role_intersection_and_account_check(monkeypatch):
    connection=NS(account_id='123456789012',role_arn='arn:aws:iam::123456789012:role/reader',external_id='external',default_region='ap-northeast-2')
    sts=MagicMock();sts.__enter__.return_value=sts
    sts.assume_role.return_value={'Credentials':{'AccessKeyId':'a','SecretAccessKey':'s','SessionToken':'t'}}
    identity=MagicMock();identity.__enter__.return_value=identity;identity.get_caller_identity.return_value={'Account':'different'}
    factory=Mock(side_effect=[sts,identity]);monkeypatch.setattr(reader.boto3,'client',factory)
    with pytest.raises(HTTPException) as e: reader.client_for(connection)
    assert e.value.status_code==403 and factory.call_count==2
    assert sts.assume_role.call_args.kwargs['Policy']==reader.POLICY


@pytest.mark.parametrize('reply', ['not-json', '{"findings":[{"title":"x","explanation":"x","confidence":"low","evidence_ids":["invented"],"checks":[]}]}'])
def test_ai_invalid_json_or_invented_citations_rejected(monkeypatch,reply):
    monkeypatch.setattr(settings,'resource_ai_enabled',True)
    provider=Mock();provider.complete_json.return_value=reply
    monkeypatch.setattr(analysis,'LLMProvider',lambda:provider)
    with pytest.raises(HTTPException) as e: analysis.analyze(observation(),'pod',{'runs':[]},True)
    assert e.value.status_code==502


def test_ai_disabled_no_provider_call(monkeypatch):
    monkeypatch.setattr(settings,'resource_ai_enabled',False)
    provider=Mock();monkeypatch.setattr(analysis,'LLMProvider',provider)
    with pytest.raises(HTTPException): analysis.analyze(observation(),'pod',{'runs':[]},True)
    provider.assert_not_called()


def test_ai_valid_citation_and_no_raw_fields(monkeypatch):
    monkeypatch.setattr(settings,'resource_ai_enabled',True)
    provider=Mock();provider.complete_json.return_value=json.dumps({'findings':[{'title':'후보','explanation':'확인 필요',
        'confidence':'low','evidence_ids':['resource'],'checks':['상태 확인']}]})
    monkeypatch.setattr(analysis,'LLMProvider',lambda:provider)
    result=analysis.analyze(observation(),'pod',{'runs':[]},True)
    assert result['mode']=='ai' and result['findings'][0]['evidence_ids']==['resource']
    assert provider.client.with_options.call_count==0 # replaced with configured client
    assert 'PRIVATE' not in provider.complete_json.call_args.args[1]


def test_aws_sdk_schema_and_partial_permissions(monkeypatch):
    import boto3
    from botocore.stub import Stubber
    c=boto3.client('ec2',region_name='ap-northeast-2',aws_access_key_id='testing',aws_secret_access_key='testing')
    with Stubber(c) as stub:
        stub.add_response('describe_vpcs',{'Vpcs':[{'VpcId':'vpc-demo','State':'available','CidrBlock':'10.0.0.0/16'}]},{'MaxResults':200})
        stub.add_response('describe_subnets',{'Subnets':[{'SubnetId':'subnet-demo','VpcId':'vpc-demo','State':'available'}]},{'MaxResults':200})
        stub.add_client_error('describe_security_groups',service_error_code='UnauthorizedOperation',service_message='PRIVATE',expected_params={'MaxResults':200})
        stub.add_response('describe_instances',{'Reservations':[{'Instances':[{'InstanceId':'i-demo','SubnetId':'subnet-demo','VpcId':'vpc-demo','State':{'Name':'running'}}]}]},{'MaxResults':200})
        monkeypatch.setattr(reader,'client_for',lambda _:c)
        result=reader.observe(NS(id=uuid4()),NS(account_id='123456789012',default_region='ap-northeast-2'))
        assert result['status']=='partial' and len(result['items'])==3 and len(result['relations'])==3
        assert result['outcomes'][2]['status']=='error' and 'PRIVATE' not in json.dumps(result)
        stub.assert_no_pending_responses()


def test_terrakube_permission_denial_prevents_history_read(monkeypatch):
    from datetime import datetime,timezone
    t=target();user=NS(id=t.owner_id)
    link=NS(canvas_id=uuid4(),created_at=datetime.now(timezone.utc))
    canvas=NS(id=link.canvas_id,name='Bound',execution_backend='terrakube',terrakube_workspace_id=str(uuid4()))
    db=Mock();db.scalar.side_effect=[link,canvas]
    monkeypatch.setattr(execution.terrakube,'require_access',Mock(side_effect=HTTPException(403,'not allowed')))
    result=execution.context(db,t,user,'key','pod',True)
    assert result['runs']==[] and result['error']=='not allowed'
    db.scalars.assert_not_called()
