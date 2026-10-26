"""Revalidate current access before serving either live or saved data."""
import hashlib
import json
from fastapi import HTTPException
from eolgae.integrations.kubernetes.access import scope_for, NAMESPACE
from eolgae.models.aws_connection import AwsConnection


def connection_for(db, target):
    connection = db.get(AwsConnection, target.aws_connection_id) if target.aws_connection_id else None
    if (not connection or connection.owner_id != target.owner_id or connection.binding_status != 'verified'
            or not connection.role_arn or not connection.external_id):
        raise HTTPException(409, '소유한 verified AWS Connection을 Target에 연결하세요.')
    return connection


def scope(db, target):
    if target.archived_at or target.deleted_at:
        raise HTTPException(409, '보관되거나 삭제된 Target은 조회할 수 없습니다.')
    if target.kind == 'kubernetes_cluster':
        return {**scope_for(target), 'provider': 'kubernetes', 'label': 'Namespace'}
    if target.kind == 'aws_account':
        connection = connection_for(db, target)
        return {'namespaces': [connection.default_region], 'default_namespace': connection.default_region,
                'provider': 'aws', 'label': 'Region'}
    raise HTTPException(409, '지원하지 않는 Target입니다.')


def authorize_scope(db, target, namespace=None):
    permitted = scope(db, target)
    value = namespace if namespace is not None else permitted['default_namespace']
    allowed = permitted['namespaces']
    if (permitted['provider'] == 'kubernetes' and value != '*' and not NAMESPACE.fullmatch(value)):
        raise HTTPException(422, '올바른 namespace를 입력하세요.')
    if '*' not in allowed and value not in allowed:
        raise HTTPException(403, '허용되지 않은 조회 범위입니다.')
    identity = {'target': str(target.id), 'kind': target.kind, 'endpoint': target.endpoint,
                'secret_ref': target.secret_ref, 'connection': str(target.aws_connection_id), 'scope': value}
    if target.kind == 'aws_account':
        c = connection_for(db, target)
        identity.update(account=c.account_id, role=c.role_arn)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return value, key
