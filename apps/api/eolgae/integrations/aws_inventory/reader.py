"""Account-bound, read-only STS session and bounded EC2 inventory."""
import json
from contextlib import closing
import re
import time
from datetime import datetime, timezone
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from .normalize import normalize

KINDS = {'VPC': ('describe_vpcs', 'Vpcs'), 'Subnet': ('describe_subnets', 'Subnets'),
         'SecurityGroup': ('describe_security_groups', 'SecurityGroups'), 'EC2': ('describe_instances', 'Reservations')}
ACTIONS = ['ec2:DescribeVpcs', 'ec2:DescribeSubnets', 'ec2:DescribeSecurityGroups', 'ec2:DescribeInstances']
POLICY = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Action': ACTIONS, 'Resource': '*'}]})
CONFIG = Config(connect_timeout=3, read_timeout=5, retries={'max_attempts': 0})


def client_for(connection):
    if (not re.fullmatch(r'\d{12}', connection.account_id)
            or not re.fullmatch(r'arn:(aws|aws-cn|aws-us-gov):iam::' + connection.account_id + r':role/[\w+=,.@/-]+', connection.role_arn)):
        raise HTTPException(409, 'AWS 계정과 Role ARN이 일치하지 않습니다.')
    region = connection.default_region
    if region not in boto3.Session().get_available_regions('ec2', partition_name=connection.role_arn.split(':')[1]):
        raise HTTPException(422, '지원하는 AWS Region을 설정하세요.')
    try:
        with closing(boto3.client('sts', region_name=region, config=CONFIG)) as sts:
            result = sts.assume_role(RoleArn=connection.role_arn, ExternalId=connection.external_id,
                RoleSessionName='eolgae-inventory', DurationSeconds=900, Policy=POLICY)
        creds = result['Credentials']
        args = dict(aws_access_key_id=creds['AccessKeyId'], aws_secret_access_key=creds['SecretAccessKey'],
                    aws_session_token=creds['SessionToken'], region_name=region, config=CONFIG)
        with closing(boto3.client('sts', **args)) as identity:
            if identity.get_caller_identity()['Account'] != connection.account_id:
                raise HTTPException(403, 'AWS 계정 확인에 실패했습니다.')
        return boto3.client('ec2', **args)
    except (BotoCoreError, ClientError, KeyError):
        raise HTTPException(502, 'AWS 조회 Role 또는 STS 연결을 확인하세요.') from None


def collect(client, operation, result_key, deadline):
    values, cursor = [], None
    for _ in range(5):
        if time.monotonic() > deadline:
            raise TimeoutError()
        body = getattr(client, operation)(MaxResults=200, **({'NextToken': cursor} if cursor else {}))
        page = body[result_key]
        if result_key == 'Reservations':
            page = [instance for reservation in page for instance in reservation.get('Instances', [])]
        values.extend(page)
        cursor = body.get('NextToken')
        if len(values) > 1000:
            return values[:1000], False
        if not cursor:
            return values, True
    return values, False


def observe(target, connection):
    stamp = datetime.now(timezone.utc).isoformat()
    items, edges, outcomes = [], [], []
    deadline = time.monotonic() + 30
    with closing(client_for(connection)) as client:
        for kind, (operation, result_key) in KINDS.items():
            try:
                values, complete = collect(client, operation, result_key, deadline)
                normalized, relations = normalize(kind, values, connection, stamp)
                items.extend(normalized); edges.extend(relations)
                outcomes.append({'kind': kind, 'complete': complete, 'status': 'success' if complete else 'incomplete',
                                 'count': len(normalized), 'message': '' if complete else '페이지 제한: 일부 목록만 조회됨'})
            except (BotoCoreError, ClientError, TimeoutError, ValueError, KeyError, TypeError):
                outcomes.append({'kind': kind, 'complete': False, 'status': 'error', 'count': 0,
                                 'code': 'aws_read_failed', 'message': 'AWS 조회 권한·연결·응답을 확인하세요.'})
    ids = {r['uid'] for r in items}
    complete = all(o['complete'] for o in outcomes)
    return {'target_id': str(target.id), 'namespace': connection.default_region, 'provider': 'aws',
            'observed_at': stamp, 'complete': complete,
            'status': 'success' if complete else 'partial' if items else 'error',
            'items': items, 'relations': [e for e in edges if e['source_uid'] in ids and e['target_uid'] in ids],
            'relations_complete': complete, 'outcomes': outcomes, 'signals': [],
            'signal_outcome': {'status': 'unsupported', 'message': 'AWS 운영 신호 수집은 아직 지원하지 않습니다.'}}
