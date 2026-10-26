"""Operational evidence without event messages, container args or environment."""
import re
from .client import Reader, ReadError

REASONS = {'CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull', 'OOMKilled', 'CreateContainerConfigError'}


def workload_signals(raw, stamp):
    signals = []
    for kind, obj in raw:
        meta, status = obj.get('metadata') or {}, obj.get('status') or {}
        uid = meta.get('uid')
        if kind == 'Pod':
            for index, container in enumerate(status.get('containerStatuses') or []):
                for state in ('state', 'lastState'):
                    for phase in ('waiting', 'terminated'):
                        reason = ((container.get(state) or {}).get(phase) or {}).get('reason')
                        if reason in REASONS:
                            signals.append({'id': f'{uid}:{index}:{state}:{reason}', 'uid': uid, 'type': 'Warning',
                                            'reason': reason, 'count': 1, 'at': stamp, 'source': 'Pod status'})
        if kind == 'Deployment':
            for c in status.get('conditions') or []:
                if c.get('type') == 'Progressing' and c.get('status') == 'False':
                    signals.append({'id': f'{uid}:progress', 'uid': uid, 'type': 'Warning',
                                    'reason': 'DeploymentNotProgressing', 'count': 1, 'at': stamp, 'source': 'Deployment condition'})
    return signals[:1000]


def event_signals(access, items, stamp):
    known = {r['uid']: r for r in items}
    try:
        with Reader(access) as reader:
            values, complete = reader.collect('Event')
        signals = []
        for item in values:
            involved = item.get('involvedObject') or {}
            resource = known.get(involved.get('uid'))
            if not resource or involved.get('namespace', '') != resource['namespace']:
                continue
            # Free-text messages may contain secrets; retain only a short reason code.
            reason = str(item.get('reason') or '')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,79}', reason):
                reason = 'EventObserved'
            signals.append({'id': str((item.get('metadata') or {}).get('uid', ''))[:200],
                'uid': resource['uid'], 'reason': reason, 'type': 'Warning' if item.get('type') == 'Warning' else 'Normal',
                'count': max(1, int(item.get('count') or 1)),
                'at': str(item.get('lastTimestamp') or item.get('eventTime') or stamp)[:64], 'source': 'Kubernetes Event'})
        return signals[:1000], {'status': 'success' if complete else 'incomplete',
                                'message': '' if complete else 'Events 일부만 조회됨'}
    except (ReadError, ValueError, TypeError, AttributeError):
        return [], {'status': 'error', 'message': 'Events 권한 또는 연결 확인 필요; 리소스 관측은 별도로 유지됩니다.'}
