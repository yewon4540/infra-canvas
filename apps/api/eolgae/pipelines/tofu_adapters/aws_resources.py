"""AWS resource HCL renderers."""
from __future__ import annotations

from typing import Any

from eolgae.pipelines.graph_model import InferredStructure


def render_aws_resource(
    *,
    node_type: str,
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str] | None = None,
) -> str:
    if node_type == "aws.ec2.instance":
        return _ec2_instance(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.ec2.alb":
        return _alb(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.ec2.asg":
        return _asg(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.rds.db_instance":
        return _rds(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.s3.bucket":
        return _s3_bucket(tf_name, props, depends_on_block, system_tags or {})
    if node_type == "aws.ec2.security_group":
        return _security_group(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.iam.role":
        return _iam_role(tf_name, props, depends_on_block, system_tags or {})
    if node_type == "aws.route53.record":
        return _route53_record(tf_name, props, depends_on_block)
    if node_type == "aws.ec2.vpc":
        return _vpc(tf_name, props, depends_on_block, system_tags or {})
    if node_type == "aws.ec2.subnet":
        return _subnet(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.ec2.internet_gateway":
        return _internet_gateway(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.ec2.nat_gateway":
        return _nat_gateway(tf_name, props, depends_on_block, inferred, system_tags or {})
    if node_type == "aws.ec2.route_table":
        return _route_table(tf_name, props, depends_on_block, inferred, system_tags or {})
    return ""


def _ec2_instance(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    instance_type = props.get("instance_type", "t3.micro")
    ami_id = props.get("ami_id") or "ami-CHANGE_ME"
    sg_ids = props.get("security_group_ids", "")
    subnet_ref = inferred.subnet_refs[0] if inferred.subnet_refs else None
    subnet_line = (
        f"\n  subnet_id     = {subnet_ref}.id"
        if subnet_ref
        else "\n  # subnet_id     = ...  # Subnet Group 안에 배치하면 자동 연결"
    )
    sg_line = (
        "\n  vpc_security_group_ids = ["
        + ", ".join(f"{ref}.id" for ref in inferred.security_group_refs)
        + "]"
        if inferred.security_group_refs
        else f"\n  # vpc_security_group_ids = [...]  # 입력값: {sg_ids!r}"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_instance" "{tf_name}" {{
  instance_type = "{instance_type}"
  ami           = "{ami_id}"{subnet_line}
  {sg_line.strip()}{tags_block}{depends_on_block}
}}"""


def _alb(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    scheme = props.get("scheme", "internet-facing")
    is_internal = scheme == "internal"
    sg_ids = props.get("security_group_ids", "")
    listener_port = props.get("listener_port", 80)
    subnet_line = (
        "subnets           = ["
        + ", ".join(f"{ref}.id" for ref in inferred.subnet_refs)
        + "]"
        if inferred.subnet_refs
        else "# subnets         = [...]  # Subnet Group 안에 배치하면 자동 연결"
    )
    sg_line = (
        "security_groups    = ["
        + ", ".join(f"{ref}.id" for ref in inferred.security_group_refs)
        + "]"
        if inferred.security_group_refs
        else f"# security_groups = [...]  # 입력값: {sg_ids!r}"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_lb" "{tf_name}" {{
  internal           = {str(is_internal).lower()}
  load_balancer_type = "application"
  {sg_line}
  {subnet_line}{tags_block}{depends_on_block}
}}

# listener (port {listener_port}) 는 별도 정의 필요"""


def _rds(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    engine = props.get("engine", "postgres")
    instance_class = props.get("instance_class", "db.t3.micro")
    multi_az = bool(props.get("multi_az", False))
    sg_ids = props.get("security_group_ids", "")
    subnet_refs = inferred.subnet_refs
    db_subnet_group = (
        f'\n  db_subnet_group_name = aws_db_subnet_group.{tf_name}.name'
        if subnet_refs
        else "\n  # db_subnet_group_name = ...  # Subnet Group 안에 배치하면 자동 연결"
    )
    sg_line = (
        "\n  vpc_security_group_ids = ["
        + ", ".join(f"{ref}.id" for ref in inferred.security_group_refs)
        + "]"
        if inferred.security_group_refs
        else f"\n  # vpc_security_group_ids = [...]  # 입력값: {sg_ids!r}"
    )
    subnet_group_block = (
        f"""\n\nresource "aws_db_subnet_group" "{tf_name}" {{
  name       = "{tf_name}"
  subnet_ids = [{", ".join(f"{ref}.id" for ref in subnet_refs)}]{_tags_block(_merged_tags(props, system_tags))}
}}"""
        if subnet_refs
        else ""
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_db_instance" "{tf_name}" {{
  engine              = "{engine}"
  instance_class      = "{instance_class}"
  allocated_storage   = 20
  multi_az            = {str(multi_az).lower()}
  skip_final_snapshot = true
  username            = "admin"
  password            = "CHANGE_ME"  # 운영 시 secrets manager 사용 권장
  {db_subnet_group.strip()}
  {sg_line.strip()}{tags_block}{depends_on_block}
}}{subnet_group_block}"""


def _merged_tags(props: dict[str, Any], system_tags: dict[str, str]) -> dict[str, Any]:
    user_tags = props.get("tags") or {}
    if not isinstance(user_tags, dict):
        user_tags = {}
    return {**user_tags, **system_tags}


def _tags_block(tags: dict[str, Any]) -> str:
    if not tags:
        return ""
    lines = [
        f'    {key} = "{str(value)}"'
        for key, value in sorted(tags.items())
        if key and value is not None
    ]
    if not lines:
        return ""
    return "\n  tags = {\n" + "\n".join(lines) + "\n  }"


def _s3_bucket(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    system_tags: dict[str, str],
) -> str:
    bucket_name = props.get("bucket_name") or f"bucket-{tf_name}"
    versioning = bool(props.get("versioning", False))
    public_block = bool(props.get("public_access_block", True))
    tags_block = _tags_block(_merged_tags(props, system_tags))

    out = [f"""resource "aws_s3_bucket" "{tf_name}" {{
  bucket = "{bucket_name}"{tags_block}{depends_on_block}
}}"""]

    if versioning:
        out.append(
            f"""resource "aws_s3_bucket_versioning" "{tf_name}_versioning" {{
  bucket = aws_s3_bucket.{tf_name}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}"""
        )

    if public_block:
        out.append(
            f"""resource "aws_s3_bucket_public_access_block" "{tf_name}_pab" {{
  bucket                  = aws_s3_bucket.{tf_name}.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}"""
        )

    return "\n\n".join(out)


def _asg(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    min_size = int(props.get("min_size", 1))
    max_size = int(props.get("max_size", 3))
    desired = int(props.get("desired_capacity", 1))
    template = props.get("instance_template") or ""
    subnet_line = (
        "vpc_zone_identifier = ["
        + ", ".join(f"{ref}.id" for ref in inferred.subnet_refs)
        + "]"
        if inferred.subnet_refs
        else "# vpc_zone_identifier = [...]  # Subnet Group 안에 배치하면 자동 연결"
    )
    tag_blocks = _asg_tag_blocks(_merged_tags(props, system_tags))
    return f"""resource "aws_autoscaling_group" "{tf_name}" {{
  min_size            = {min_size}
  max_size            = {max_size}
  desired_capacity    = {desired}
  {subnet_line}
  # launch_template {{ id = ...; version = "$Latest" }}  # 입력값: {template!r}{tag_blocks}{depends_on_block}
}}"""


def _asg_tag_blocks(tags: dict[str, Any]) -> str:
    if not tags:
        return ""
    blocks = []
    for key, value in sorted(tags.items()):
        if not key or value is None:
            continue
        blocks.append(
            f"""
  tag {{
    key                 = "{key}"
    value               = "{str(value)}"
    propagate_at_launch = true
  }}"""
        )
    return "".join(blocks)


def _security_group(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    ingress = props.get("ingress_rules") or ""
    egress = props.get("egress_rules") or ""
    vpc_line = (
        f"vpc_id = {inferred.vpc_ref}.id"
        if inferred.vpc_ref
        else "# vpc_id = ...  # VPC/Subnet Group 안에 배치하면 자동 연결"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_security_group" "{tf_name}" {{
  name = "{tf_name}"
  {vpc_line}
  # ingress 룰 입력값: {ingress!r}
  # egress 룰 입력값: {egress!r}
  # 실 변환: aws_vpc_security_group_ingress_rule / _egress_rule 리소스로 분리 권장{tags_block}{depends_on_block}
}}"""


def _iam_role(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    system_tags: dict[str, str],
) -> str:
    principal = props.get("assume_role_policy") or "ec2"
    policies = props.get("attached_policies") or ""
    principal_service = (
        principal if principal.endswith(".amazonaws.com") else f"{principal}.amazonaws.com"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_iam_role" "{tf_name}" {{
  name = "{tf_name}"
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{ Service = "{principal_service}" }}
      Action = "sts:AssumeRole"
    }}]
  }}){tags_block}{depends_on_block}
}}

# attached_policies 입력값: {policies!r}
# 실 변환: aws_iam_role_policy_attachment 리소스로 ARN 마다 분리"""


def _vpc(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    system_tags: dict[str, str],
) -> str:
    cidr = props.get("cidr") or "10.0.0.0/16"
    region = props.get("region") or ""
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_vpc" "{tf_name}" {{
  cidr_block           = "{cidr}"
  enable_dns_hostnames = true
  enable_dns_support   = true
  # region 입력값: {region!r} — provider 블록의 region 으로 결정됨{tags_block}{depends_on_block}
}}"""


def _internet_gateway(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    vpc_line = (
        f"vpc_id = {inferred.vpc_ref}.id"
        if inferred.vpc_ref
        else "# vpc_id = ...  # VPC Group 안에 배치하면 자동 연결"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_internet_gateway" "{tf_name}" {{
  {vpc_line}{tags_block}{depends_on_block}
}}"""


def _nat_gateway(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    eip = props.get("elastic_ip_id") or ""
    subnet_ref = inferred.subnet_refs[0] if inferred.subnet_refs else None
    eip_line = (
        f'allocation_id = "{eip}"'
        if eip
        else "# allocation_id = aws_eip.<name>.id  # EIP 노드 미지원 — 별도 aws_eip 리소스 생성 필요"
    )
    subnet_line = (
        f"subnet_id     = {subnet_ref}.id"
        if subnet_ref
        else "# subnet_id     = ...  # Public Subnet Group 안에 배치하면 자동 연결"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_nat_gateway" "{tf_name}" {{
  {eip_line}
  {subnet_line}{tags_block}{depends_on_block}
}}"""


def _route_table(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    routes = props.get("routes") or []
    vpc_line = (
        f"vpc_id = {inferred.vpc_ref}.id"
        if inferred.vpc_ref
        else "# vpc_id = ...  # VPC/Subnet Group 안에 배치하면 자동 연결"
    )
    route_blocks: list[str] = []
    if inferred.route_gateway_refs:
        route_items = routes if isinstance(routes, list) and routes else [{}]
        for idx, (target_attr, target_ref) in enumerate(inferred.route_gateway_refs):
            route = route_items[min(idx, len(route_items) - 1)]
            cidr_block = (
                route.get("cidr_block")
                if isinstance(route, dict)
                else None
            ) or "0.0.0.0/0"
            route_blocks.append(
                f"""
  route {{
    cidr_block = "{cidr_block}"
    {target_attr} = {target_ref}.id
  }}"""
            )

    route_note = ""
    if not route_blocks:
        route_note = f"\n  # 운영자 입력 routes: {routes!r}"
        route_note += "\n  # route edge를 IGW/NAT Gateway에 연결하면 route block 자동 생성"
    tags_block = _tags_block(_merged_tags(props, system_tags))

    associations = [
        f"""
resource "aws_route_table_association" "{tf_name}_{idx + 1}" {{
  subnet_id      = {subnet_ref}.id
  route_table_id = aws_route_table.{tf_name}.id
}}"""
        for idx, subnet_ref in enumerate(inferred.route_subnet_refs)
    ]

    route_table = f"""resource "aws_route_table" "{tf_name}" {{
  {vpc_line}
{"".join(route_blocks)}{route_note}{tags_block}{depends_on_block}
}}"""
    return "\n\n".join([route_table, *associations])


def _subnet(
    tf_name: str,
    props: dict[str, Any],
    depends_on_block: str,
    inferred: InferredStructure,
    system_tags: dict[str, str],
) -> str:
    cidr = props.get("cidr") or "10.0.1.0/24"
    az = props.get("availability_zone") or "CHANGE_ME"
    subnet_type = props.get("type") or "private"
    map_public = "true" if subnet_type == "public" else "false"
    vpc_line = (
        f"vpc_id                  = {inferred.vpc_ref}.id"
        if inferred.vpc_ref
        else "# vpc_id                  = ...  # VPC Group 안에 배치하면 자동 연결"
    )
    tags_block = _tags_block(_merged_tags(props, system_tags))
    return f"""resource "aws_subnet" "{tf_name}" {{
  {vpc_line}
  cidr_block              = "{cidr}"
  availability_zone       = "{az}"
  map_public_ip_on_launch = {map_public}  # type={subnet_type!r}{tags_block}{depends_on_block}
}}"""


def _route53_record(tf_name: str, props: dict[str, Any], depends_on_block: str) -> str:
    zone_id = props.get("zone_id") or "ZONE_ID_CHANGE_ME"
    record_type = props.get("record_type") or "A"
    value = props.get("value") or ""
    return f"""resource "aws_route53_record" "{tf_name}" {{
  zone_id = "{zone_id}"
  name    = "{tf_name}"  # 운영 시 실 도메인명으로 변경
  type    = "{record_type}"
  ttl     = 300
  records = ["{value}"]{depends_on_block}
}}"""
