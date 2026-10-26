"""Owner/scope checked resource observation and operational context endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from eolgae.auth.dependencies import get_current_user
from eolgae.db import get_db
from eolgae.models.user import User
from eolgae.models.target import Target
from eolgae.routers.targets import _owned_target
from eolgae.services.resource_observation import observe
from eolgae.services.resources import access, snapshots, execution, analysis
from eolgae.integrations.aws_inventory import reader as aws_reader

router = APIRouter(prefix='/targets', tags=['resources'])


def live(db, target, namespace):
    if target.kind == 'aws_account':
        return aws_reader.observe(target, access.connection_for(db, target))
    return observe(target, namespace, include_signals=True)


@router.get('/{target_id}/resource-scope')
def resource_scope(target_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return access.scope(db, _owned_target(db, target_id, user))


@router.get('/{target_id}/resources')
def list_resources(target_id: UUID, namespace: str | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _owned_target(db, target_id, user)
    namespace, _ = access.authorize_scope(db, target, namespace)
    return live(db, target, namespace)


@router.post('/{target_id}/observations')
def collect_observation(target_id: UUID, namespace: str | None = None,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _owned_target(db, target_id, user)
    namespace, key = access.authorize_scope(db, target, namespace)
    result = live(db, target, namespace)
    # Recheck scope after I/O in case operator profile changed during collection.
    _, current_key = access.authorize_scope(db, target, namespace)
    if key != current_key:
        raise HTTPException(409, '조회 설정이 변경되었습니다. 다시 조회하세요.')
    return snapshots.save(db, target, key, result)


@router.get('/{target_id}/observations')
def observation_history(target_id: UUID, namespace: str | None = None,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _owned_target(db, target_id, user)
    _, key = access.authorize_scope(db, target, namespace)
    row = snapshots.latest(db, target, key)
    return {'latest': snapshots.public(row) if row else None, 'history': snapshots.history(db, target, key)}


@router.get('/{target_id}/observations/{observation_id}')
def observation_detail(target_id: UUID, observation_id: UUID, namespace: str | None = None,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = _owned_target(db, target_id, user)
    _, key = access.authorize_scope(db, target, namespace)
    return snapshots.public(snapshots.get_snapshot(db, target, key, observation_id))


class ResourceRequest(BaseModel):
    observation_id: UUID
    uid: str = Field(min_length=1, max_length=300)
    namespace: str = Field(min_length=1, max_length=100)


class LinkRequest(ResourceRequest):
    canvas_id: UUID | None = None


class AnalysisRequest(ResourceRequest):
    use_ai: bool = False


def checked_resource(db, user, target_id, body):
    target = _owned_target(db, target_id, user)
    _, key = access.authorize_scope(db, target, body.namespace)
    row = snapshots.get_snapshot(db, target, key, body.observation_id)
    if not any(r['uid'] == body.uid for r in row.payload['items']):
        raise HTTPException(404, '관측된 리소스를 찾을 수 없습니다.')
    return target, key, row


@router.get('/{target_id}/resource-context')
def resource_context(target_id: UUID, observation_id: UUID, uid: str = Query(max_length=300),
                     namespace: str = Query(max_length=100), live_runs: bool = False,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = ResourceRequest(observation_id=observation_id, uid=uid, namespace=namespace)
    target, key, _ = checked_resource(db, user, target_id, body)
    return {**execution.context(db, target, user, key, uid, live_runs),
            'candidates': execution.candidates(db, target, user)}


@router.put('/{target_id}/resource-context')
def link_context(target_id: UUID, body: LinkRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target, key, _ = checked_resource(db, user, target_id, body)
    db.execute(select(Target.id).where(Target.id == target.id).with_for_update())
    execution.bind(db, target, user, key, body.uid, body.canvas_id)
    return {'ok': True}


@router.post('/{target_id}/resource-analysis')
def resource_analysis(target_id: UUID, body: AnalysisRequest,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target, key, row = checked_resource(db, user, target_id, body)
    runs = execution.context(db, target, user, key, body.uid)
    return analysis.analyze(row.payload, body.uid, runs, body.use_ai)
