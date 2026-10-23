from __future__ import annotations
import json
import ssl
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from eolgae.config import settings
from eolgae.integrations.kubernetes import access, client, normalize
from eolgae.routers import resources
from eolgae.services import resource_observation as service
from eolgae.services.target_verification import verify_kubernetes_target


@pytest.fixture
def target():
    return SimpleNamespace(id=uuid4(), owner_id=uuid4(), kind="kubernetes_cluster",
        endpoint="https://cluster.example.com:6443", secret_ref={"name":"reader"},
        config={"default_namespace":"demo"}, archived_at=None, deleted_at=None)


@pytest.fixture
def profile(tmp_path, monkeypatch, target):
    data={"name":"reader","endpoint":target.endpoint,"user_ids":[str(target.owner_id)],
          "namespaces":["demo"],"token_file":str(tmp_path/'token'),"ca_file":str(tmp_path/'ca')}
    path=tmp_path/'profiles.json';path.write_text(json.dumps([data]))
    monkeypatch.setattr(settings,"kubernetes_read_profiles_file",str(path))
    return data,path


@pytest.mark.parametrize('field,value', [('owner_id',uuid4()),('endpoint','https://elsewhere.example.com'),('secret_ref',{'name':'other'})])
def test_profile_binds_user_endpoint_and_reference(target,profile,field,value):
    setattr(target,field,value)
    with pytest.raises(HTTPException) as error: access.profile_for(target)
    assert error.value.status_code==403


@pytest.mark.parametrize('namespace', ['other','*','../secrets','a/b','Demo',''])
def test_scope_denied_before_reading_credentials(target,profile,namespace):
    with pytest.raises(HTTPException) as error: access.access_for(target,namespace)
    assert error.value.status_code in (403,422)


def test_scope_defaults_to_allowed_namespace(target,profile):
    target.config={'default_namespace':'outside'}
    assert access.scope_for(target)=={'namespaces':['demo'],'default_namespace':'demo'}


def test_bad_ca_and_token_do_not_leak(target,profile):
    data,_=profile
    from pathlib import Path
    Path(data['token_file']).write_text('private-token')
    Path(data['ca_file']).write_text('not-a-certificate')
    with pytest.raises(HTTPException) as error: access.access_for(target,'demo')
    assert error.value.status_code==503
    assert 'private-token' not in str(error.value.detail)


def reader(handler,ns='demo'):
    a=access.Access('https://cluster.example.com','private-token',ssl.create_default_context(),ns,[ns])
    return client.Reader(a,transport=httpx.MockTransport(handler))


def test_get_only_pagination_and_namespace():
    calls=[]
    def handle(request):
        calls.append(request)
        assert request.method=='GET'
        assert request.url.path=='/api/v1/namespaces/demo/pods'
        assert request.url.params['limit']=='200'
        if len(calls)==1:
            return httpx.Response(200,json={'items':[{'metadata':{'uid':'a'}}],'metadata':{'continue':'next'}})
        assert request.url.params['continue']=='next'
        return httpx.Response(200,json={'items':[{'metadata':{'uid':'b'}}]})
    with reader(handle) as r: items,complete=r.collect('Pod')
    assert complete and len(items)==2


def test_namespace_only_uses_single_namespace_get():
    def handle(request):
        assert request.url.path=='/api/v1/namespaces/demo'
        return httpx.Response(200,json={'metadata':{'name':'demo','uid':'ns'}})
    with reader(handle) as r: items,complete=r.collect('Namespace')
    assert complete and items[0]['metadata']['name']=='demo'


def test_page_limit_is_not_complete():
    with reader(lambda req:httpx.Response(200,json={'items':[{}],'metadata':{'continue':'next'}})) as r:
        items,complete=r.collect('Pod')
    assert not complete and len(items)==client.MAX_PAGES


@pytest.mark.parametrize('code',[301,401,403,404,410,429,500])
def test_remote_errors_are_redacted_and_redirect_not_followed(code):
    calls=[]
    def handle(req):
        calls.append(req)
        return httpx.Response(code,text='private-token credentials',headers={'Location':'https://outside.example.com'})
    with reader(handle) as r, pytest.raises(client.ReadError) as error: r.collect('Pod')
    assert len(calls)==1 and 'private-token' not in error.value.message


def test_timeout_and_payload_limit(monkeypatch):
    def timeout(req): raise httpx.ReadTimeout('private-token',request=req)
    with reader(timeout) as r, pytest.raises(client.ReadError) as error: r.collect('Pod')
    assert error.value.code=='timeout'
    monkeypatch.setattr(client,'MAX_BYTES',10)
    with reader(lambda req:httpx.Response(200,content=b'x'*11)) as r, pytest.raises(client.ReadError) as error:
        r.collect('Pod')
    assert error.value.code=='limit'


def obj(kind,uid,name,ns='demo',**kwargs):
    return {'kind':kind,'metadata':{'uid':uid,'name':name,'namespace':ns},**kwargs}


def test_relations_are_scoped_and_raw_secrets_not_returned():
    deploy=obj('Deployment','d','web')
    rs=obj('ReplicaSet','r','web-rs');rs['metadata']['ownerReferences']=[{'uid':'d','kind':'Deployment','name':'web'}]
    pod=obj('Pod','p','web-pod',spec={'containers':[{'env':[{'name':'PASSWORD','value':'secret-value'}]}]},status={'phase':'Running'})
    pod['metadata'].update(labels={'app':'web'},annotations={'secret':'secret-value'},ownerReferences=[{'uid':'r','kind':'ReplicaSet','name':'web-rs'}])
    other=obj('Pod','other','foreign','other');other['metadata']['labels']={'app':'web'}
    svc=obj('Service','s','web',spec={'selector':{'app':'web'}})
    ingress=obj('Ingress','i','web',spec={'defaultBackend':{'service':{'name':'web'}}})
    raw=[(o['kind'],o) for o in [deploy,rs,pod,other,svc,ingress]]
    items=[normalize.resource(o,k,'now') for k,o in raw]
    edges=normalize.relations(raw,items)
    assert {(e['source_uid'],e['target_uid']) for e in edges}=={('d','r'),('r','p'),('s','p'),('i','s')}
    assert 'secret-value' not in json.dumps(items)
    assert normalize.resource(svc,'Service','now')['status']=='Observed'


def test_partial_success_and_live_verification(target,monkeypatch):
    monkeypatch.setattr(service,'access_for',lambda t,n:SimpleNamespace(namespace='demo'))
    class Partial:
        def __init__(self,a): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def collect(self,kind):
            if kind=='Ingress': raise client.ReadError('403','조회 권한 부족')
            return ([obj(kind,kind,kind.lower())] if kind=='Pod' else []),True
    monkeypatch.setattr(service,'Reader',Partial)
    monkeypatch.setattr(settings,'kubernetes_read_profiles_file','configured')
    result=service.observe(target)
    assert result['status']=='partial' and not result['complete']
    assert len(result['items'])==1
    verification=verify_kubernetes_target(target)
    assert verification.status=='error' and not verification.ok


def test_owner_check_precedes_any_remote_access(target,monkeypatch):
    db=Mock();db.get.return_value=target
    observe=Mock();monkeypatch.setattr(resources,'observe',observe)
    with pytest.raises(HTTPException) as error:
        resources.list_resources(target.id,user=SimpleNamespace(id=uuid4()),db=db)
    assert error.value.status_code==404
    observe.assert_not_called()


def test_archived_target_is_not_readable(target,profile):
    target.archived_at='now'
    with pytest.raises(HTTPException) as error: access.profile_for(target)
    assert error.value.status_code==409
