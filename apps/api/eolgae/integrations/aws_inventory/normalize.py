"""Allowlisted EC2 metadata only; tags, user data and credentials are not returned."""
IDS = {'VPC': 'VpcId', 'Subnet': 'SubnetId', 'SecurityGroup': 'GroupId', 'EC2': 'InstanceId'}


def normalize(kind, values, connection, stamp):
    prefix = f'aws:{connection.account_id}:{connection.default_region}:'
    items, edges = [], []
    for value in values:
        name = value[IDS[kind]]
        uid = prefix + name
        if kind == 'EC2':
            state = value.get('State', {}).get('Name', 'unknown')
            summary = {'instance_type': value.get('InstanceType', ''), 'zone': value.get('Placement', {}).get('AvailabilityZone', '')}
        elif kind == 'SecurityGroup':
            state, summary = 'Observed', {'vpc': value.get('VpcId', '')}
        else:
            state = value.get('State', 'unknown')
            summary = {'cidr': value.get('CidrBlock', ''), 'vpc': value.get('VpcId', '')}
        items.append({'uid': uid, 'name': name, 'kind': kind, 'namespace': connection.default_region,
                      'status': state, 'summary': summary, 'observed_at': stamp, 'management': '미확인'})
        for key, evidence in [('VpcId', 'awsVpc'), ('SubnetId', 'awsSubnet')]:
            if value.get(key) and value[key] != name:
                edges.append({'source_uid': prefix + value[key], 'target_uid': uid, 'evidence': evidence})
        for group in value.get('SecurityGroups', []):
            edges.append({'source_uid': prefix + group['GroupId'], 'target_uid': uid, 'evidence': 'awsSecurityGroup'})
    return items, edges
