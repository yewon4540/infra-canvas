"""Explicit UID-to-Canvas context. Never infer execution ownership from a name."""
from fastapi import HTTPException
from sqlalchemy import select
from eolgae.integrations import terrakube
from eolgae.models.canvas import Canvas
from eolgae.models.deployment import AuditLog, Deployment
from eolgae.models.remote_plan import RemotePlan
from eolgae.models.resource_observation import ResourceExecutionLink


def canvas_query(target, user):
    return select(Canvas).where(Canvas.target_id == target.id, Canvas.owner_id == user.id, Canvas.deleted_at.is_(None))


def candidates(db, target, user):
    return [{'id': str(c.id), 'name': c.name, 'backend': c.execution_backend} for c in
            db.scalars(canvas_query(target, user).order_by(Canvas.name).limit(100))]


def link_query(target, key, uid):
    return select(ResourceExecutionLink).where(ResourceExecutionLink.target_id == target.id,
        ResourceExecutionLink.scope_key == key, ResourceExecutionLink.resource_uid == uid)


def bind(db, target, user, key, uid, canvas_id):
    canvas = db.scalar(canvas_query(target, user).where(Canvas.id == canvas_id)) if canvas_id else None
    if canvas_id and not canvas:
        raise HTTPException(403, '동일 Target에 연결된 소유 Canvas만 선택할 수 있습니다.')
    # Serialized by the caller's Target lock; no execution/state ownership mutation.
    existing = db.scalar(link_query(target, key, uid))
    if existing:
        db.delete(existing)
        db.flush()
    if canvas:
        db.add(ResourceExecutionLink(target_id=target.id, scope_key=key, resource_uid=uid,
                                     canvas_id=canvas.id, linked_by=user.id))
    db.add(AuditLog(actor_id=user.id, action='resource.context.link', entity_type='target', entity_id=target.id,
                    after={'uid': uid, 'canvas_id': str(canvas_id) if canvas_id else None}))
    db.commit()


def context(db, target, user, key, uid, live=False):
    link = db.scalar(link_query(target, key, uid))
    canvas = db.scalar(canvas_query(target, user).where(Canvas.id == link.canvas_id)) if link else None
    result = {'binding': None, 'runs': [], 'error': None, 'has_more': False}
    if not canvas:
        return result
    result['binding'] = {'canvas_id': str(canvas.id), 'name': canvas.name, 'backend': canvas.execution_backend,
                         'workspace_id': canvas.terrakube_workspace_id, 'evidence': 'user_link',
                         'linked_at': link.created_at.isoformat()}
    if canvas.execution_backend == 'eolgae_direct':
        rows = list(db.scalars(select(Deployment).where(Deployment.canvas_id == canvas.id)
            .order_by(Deployment.created_at.desc()).limit(21)))
        result['has_more'] = len(rows) > 20
        result['runs'] = [{'id': str(r.id), 'backend': 'eolgae_direct', 'operation': r.mode,
            'status': r.status, 'created_at': r.created_at.isoformat(), 'commit': None,
            'revision': str(r.canvas_version_id), 'url': f'/canvas/{canvas.id}'} for r in rows[:20]]
    else:
        try:
            terrakube.require_access(user.id, canvas.terrakube_workspace_id)
            rows = list(db.scalars(select(RemotePlan).where(RemotePlan.canvas_id == canvas.id)
                                  .order_by(RemotePlan.created_at.desc()).limit(21)))
            result['has_more'] = len(rows) > 20
            result['runs'] = [{'id': r.job_id or str(r.id), 'backend': 'terrakube', 'operation': 'plan',
                'status': r.status, 'created_at': r.created_at.isoformat(), 'commit': r.commit_sha,
                'revision': r.canvas_revision, 'url': None} for r in rows[:20]]
            if live:
                remote = terrakube.get_jobs(canvas.terrakube_workspace_id)
                indexed = {r['id']: r for r in result['runs']}
                for r in remote['items']:
                    indexed[r['id']] = {**indexed.get(r['id'], {}), **r, 'backend': 'terrakube',
                                        'operation': indexed.get(r['id'], {}).get('operation', 'remote')}
                result['runs'] = sorted(indexed.values(), key=lambda r: r.get('created_at') or '', reverse=True)[:20]
                result['has_more'] = result['has_more'] or remote['has_more'] or len(indexed) > 20
        except HTTPException as error:
            result['error'] = str(error.detail)
    return result
