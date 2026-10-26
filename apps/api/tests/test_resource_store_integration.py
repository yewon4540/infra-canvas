"""Opt-in real PostgreSQL API test; all fixtures rolled back on the outer transaction."""
import os
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(os.environ.get('RESOURCE_DB_TEST') != '1', reason='requires migrated local PostgreSQL')


def test_persistence_context_isolation_and_ai(monkeypatch):
    from eolgae.main import app
    from eolgae.db import get_db
    from eolgae.auth.dependencies import get_current_user
    from eolgae.models import User, Target, Canvas, CanvasVersion, Deployment
    from eolgae.models.resource_observation import ResourceObservation
    from eolgae.routers import resources
    from eolgae.services.resources import access, analysis
    from eolgae.config import settings
    from test_resource_operations import observation
    engine=create_engine(settings.database_url)
    with engine.connect() as connection:
        transaction=connection.begin()
        db=Session(bind=connection,join_transaction_mode='create_savepoint')
        user=User(username='resource-test-'+uuid4().hex[:12],display_name='Resource test')
        other=User(username='other-'+uuid4().hex[:12],display_name='Other')
        db.add_all([user,other]);db.flush()
        target=Target(owner_id=user.id,name='Demo',slug=uuid4().hex,kind='kubernetes_cluster',provider='kubernetes',config={})
        foreign=Target(owner_id=other.id,name='Other',slug=uuid4().hex,kind='kubernetes_cluster',provider='kubernetes',config={})
        db.add_all([target,foreign]);db.flush()
        canvas=Canvas(owner_id=user.id,target_id=target.id,name='Explicit context',canvas_kind='kubernetes',graph={})
        wrong=Canvas(owner_id=user.id,target_id=foreign.id,name='Wrong target',graph={})
        db.add_all([canvas,wrong]);db.flush()
        version=CanvasVersion(canvas_id=canvas.id,version_number=1,graph={},author_id=user.id)
        db.add(version);db.flush()
        db.add(Deployment(canvas_id=canvas.id,canvas_version_id=version.id,status='success',mode='plan',aws_account_snapshot={},initiated_by=user.id));db.commit()
        app.dependency_overrides[get_db]=lambda:db
        app.dependency_overrides[get_current_user]=lambda:user
        monkeypatch.setattr(access,'scope_for',lambda _: {'namespaces':['demo'],'default_namespace':'demo'})
        def sample(*_):
            value=observation();value['target_id']=str(target.id);value['namespace']='demo';value['status']='success';value['relations_complete']=True
            value['observed_at']=datetime.now(timezone.utc).isoformat();value['items'][0]['observed_at']=value['observed_at']
            return value
        monkeypatch.setattr(resources,'live',sample)
        try:
            with TestClient(app) as client:
                prefix=f'/targets/{target.id}'
                saved=client.post(prefix+'/observations?namespace=demo');assert saved.status_code==200,saved.text
                data=saved.json();body={'namespace':'demo','observation_id':data['observation_id'],'uid':'pod'}
                restored=client.get(prefix+'/observations?namespace=demo').json()
                assert restored['latest']['observation_id']==data['observation_id']
                assert client.get(prefix+'/observations?namespace=*').status_code==403
                assert client.get(f'/targets/{foreign.id}/observations?namespace=demo').status_code==404
                assert client.put(prefix+'/resource-context',json={**body,'canvas_id':str(wrong.id)}).status_code==403
                assert client.put(prefix+'/resource-context',json={**body,'canvas_id':str(canvas.id)}).status_code==200
                context=client.get(prefix+'/resource-context',params=body).json()
                assert context['binding']['canvas_id']==str(canvas.id) and context['runs'][0]['operation']=='plan'
                monkeypatch.setattr(settings,'resource_ai_enabled',True)
                provider=Mock();provider.complete_json.return_value='{"findings":[{"title":"Check","explanation":"Uncertain","confidence":"low","evidence_ids":["resource"],"checks":[]}]}'
                monkeypatch.setattr(analysis,'LLMProvider',lambda:provider)
                assert client.post(prefix+'/resource-analysis',json={**body,'use_ai':True}).json()['mode']=='ai'
                for _ in range(22):
                    response=client.post(prefix+'/observations?namespace=demo');assert response.status_code==200,response.text
                assert db.scalar(select(func.count()).select_from(ResourceObservation).where(ResourceObservation.target_id==target.id))==20
                assert client.get(prefix+f'/observations/{data["observation_id"]}?namespace=demo').status_code==404
        finally:
            app.dependency_overrides.clear();db.close();transaction.rollback()
    engine.dispose()
