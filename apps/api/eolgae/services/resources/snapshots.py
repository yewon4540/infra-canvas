"""Store allowlisted observations; failed/incomplete collections never imply deletion."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import delete, select
from eolgae.models.resource_observation import ResourceObservation
from eolgae.models.target import Target


def compare_and_merge(current, previous=None):
    result = deepcopy(current)
    old = {r['uid']: r for r in (previous or {}).get('items', [])}
    fresh = {r['uid']: r for r in current['items']}
    complete = {o['kind'] for o in current['outcomes'] if o['complete']}
    changes = []
    for uid, r in fresh.items():
        before = old.get(uid)
        if not before:
            changes.append({'uid': uid, 'kind': r['kind'], 'name': r['name'],
                            'type': 'added' if previous else 'baseline', 'fields': []})
        elif r['kind'] in complete:
            fields = [k for k in ('status', 'summary') if before.get(k) != r.get(k)]
            if fields:
                changes.append({'uid': uid, 'kind': r['kind'], 'name': r['name'], 'type': 'changed', 'fields': fields,
                                'before': {k: before[k] for k in fields}, 'after': {k: r[k] for k in fields}})
    for uid, before in old.items():
        if uid not in fresh:
            if before['kind'] in complete:
                changes.append({'uid': uid, 'kind': before['kind'], 'name': before['name'], 'type': 'removed', 'fields': []})
            else:
                result['items'].append(before)
    # Retained partial results cannot grow without bound across collections.
    counts = {}
    bounded = []
    for r in result['items']:
        counts[r['kind']] = counts.get(r['kind'], 0) + 1
        if counts[r['kind']] <= 1000:
            bounded.append(r)
    result['items'] = bounded
    for uid, r in fresh.items():
        if r['kind'] == 'Pod' and 'Pod' in complete and uid in old:
            before_count = old[uid].get('summary', {}).get('restarts', '0')
            after_count = r.get('summary', {}).get('restarts', '0')
            if str(before_count).isdigit() and str(after_count).isdigit() and int(after_count) > int(before_count):
                result.setdefault('signals', []).append({'id': f'{uid}:restart-increase', 'uid': uid,
                    'type': 'Warning', 'reason': 'RestartCountIncreased', 'count': int(after_count)-int(before_count),
                    'at': current['observed_at'], 'source': 'Observation comparison'})
    result['changes'] = changes
    result['baseline_at'] = (previous or {}).get('observed_at')
    result['last_success_at'] = current['observed_at'] if current['complete'] else (previous or {}).get('last_success_at')
    return result


def query(target, key):
    return select(ResourceObservation).where(ResourceObservation.target_id == target.id, ResourceObservation.scope_key == key)


def latest(db, target, key):
    return db.scalar(query(target, key).order_by(ResourceObservation.created_at.desc(), ResourceObservation.id.desc()).limit(1))


def public(row):
    return {**row.payload, 'observation_id': str(row.id)}


def get_snapshot(db, target, key, snapshot_id):
    row = db.scalar(query(target, key).where(ResourceObservation.id == snapshot_id))
    if row is None:
        raise HTTPException(404, '이 조회 범위의 관측을 찾을 수 없습니다.')
    return row


def save(db, target, key, observation):
    # Serialize commits per Target. Network I/O has already completed.
    db.execute(select(Target.id).where(Target.id == target.id).with_for_update())
    before = latest(db, target, key)
    if before and before.payload['observed_at'] > observation['observed_at']:
        raise HTTPException(409, '더 최신 관측이 저장되었습니다. 저장된 결과를 다시 불러오세요.')
    row = ResourceObservation(target_id=target.id, scope_key=key, created_at=datetime.now(timezone.utc),
                              payload=compare_and_merge(observation, before.payload if before else None))
    db.add(row)
    db.flush()
    # At most 20 snapshots per scope, 100 per Target, and 30 days on next collection.
    scope_ids = list(db.scalars(query(target, key).order_by(ResourceObservation.created_at.desc(), ResourceObservation.id.desc()).offset(20).with_only_columns(ResourceObservation.id)))
    target_ids = list(db.scalars(select(ResourceObservation.id).where(ResourceObservation.target_id == target.id).order_by(ResourceObservation.created_at.desc(), ResourceObservation.id.desc()).offset(100)))
    if scope_ids or target_ids:
        db.execute(delete(ResourceObservation).where(ResourceObservation.id.in_(scope_ids + target_ids)))
    db.execute(delete(ResourceObservation).where(ResourceObservation.target_id == target.id,
        ResourceObservation.created_at < datetime.now(timezone.utc) - timedelta(days=30)))
    db.commit()
    return public(row)


def history(db, target, key):
    return [{'id': str(r.id), 'observed_at': r.payload['observed_at'], 'status': r.payload['status'],
             'changes': r.payload.get('changes', [])} for r in db.scalars(query(target, key)
                .order_by(ResourceObservation.created_at.desc(), ResourceObservation.id.desc()).limit(20))]
