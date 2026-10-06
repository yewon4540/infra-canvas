"""Canvas graph validation before OpenTofu plan execution."""
from __future__ import annotations

from ipaddress import ip_network
from typing import Any

from eolgae.pipelines.graph_model import GenerationContext, node_label


PLAN_REQUIREMENTS: dict[str, dict[str, bool]] = {
    "aws.ec2.instance": {"subnet": True},
    "aws.ec2.alb": {"subnet": True},
    "aws.ec2.asg": {"subnet": True},
    "aws.rds.db_instance": {"subnet": True},
    "aws.ec2.security_group": {"vpc": True},
    "aws.ec2.internet_gateway": {"vpc": True},
    "aws.ec2.nat_gateway": {"subnet": True},
    "aws.ec2.route_table": {"vpc": True},
}

def validate_canvas_for_plan(canvas_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return structured validation issues before running OpenTofu."""
    graph = canvas_data.get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    ctx = GenerationContext(nodes)
    issues: list[dict[str, Any]] = []
    edges_by_node = _edges_by_node(edges)

    for node in nodes:
        node_id = node.get("id", "")
        node_type = node.get("type", "")
        props = node.get("properties") or {}
        label = node_label(node)

        inferred = ctx.infer(node, edges_by_node.get(node_id, []))
        requirements = PLAN_REQUIREMENTS.get(node_type, {})
        if requirements.get("vpc") and not inferred.vpc_ref:
            issues.append(
                validation_issue(
                    node,
                    field="placement.vpc",
                    message="VPC 안에 배치하거나 VPC 그룹을 연결해야 함",
                    suggested_action=f"{label}을 VPC 안으로 이동하세요.",
                )
            )
        if requirements.get("subnet") and not inferred.subnet_refs:
            issues.append(
                validation_issue(
                    node,
                    field="placement.subnet",
                    message="Subnet 안에 배치하거나 같은 VPC 아래에 Subnet을 추가해야 함",
                    suggested_action=f"{label}을 Subnet 안으로 이동하거나 같은 VPC 아래에 Subnet을 추가하세요.",
                )
            )
        if node_type == "aws.ec2.alb" and len(inferred.subnet_refs) == 1:
            issues.append(
                validation_issue(
                    node,
                    field="placement.subnets",
                    message="ALB는 최소 2개 Subnet 필요",
                    suggested_action=f"{label}을 VPC 안에 배치하고 같은 VPC 아래 Subnet을 2개 이상 두세요.",
                )
            )
        if (
            node_type == "aws.rds.db_instance"
            and _truthy(props.get("multi_az"))
            and len(inferred.subnet_refs) < 2
        ):
            issues.append(
                validation_issue(
                    node,
                    field="placement.subnets",
                    message="Multi-AZ RDS는 최소 2개 Subnet 필요",
                    suggested_action=f"{label}이 참조할 Subnet을 2개 이상 배치하세요.",
                )
            )

        if node_type == "aws.ec2.subnet":
            if not _filled(props.get("cidr")):
                issues.append(
                    validation_issue(
                        node,
                        field="properties.cidr",
                        message="Subnet CIDR 입력 필요",
                        suggested_action=f"{label}의 CIDR을 입력하세요.",
                    )
                )
            elif not _valid_cidr(props.get("cidr")):
                issues.append(
                    validation_issue(
                        node,
                        field="properties.cidr",
                        message="Subnet CIDR 형식 오류",
                        suggested_action=f"{label}의 CIDR을 예: 10.0.1.0/24 형식으로 입력하세요.",
                    )
                )
            else:
                vpc = ctx.nearest_ancestor_of_type(node, "aws.ec2.vpc")
                vpc_cidr = (vpc.get("properties") or {}).get("cidr") if vpc else None
                if (
                    _filled(vpc_cidr)
                    and _valid_cidr(vpc_cidr)
                    and not _subnet_in_vpc(props.get("cidr"), vpc_cidr)
                ):
                    issues.append(
                        validation_issue(
                            node,
                            field="placement.cidr",
                            message="Subnet CIDR이 VPC CIDR 범위 밖에 있음",
                            suggested_action=f"{label}의 CIDR을 부모 VPC CIDR 안의 대역으로 조정하세요.",
                        )
                    )
            if not _filled(props.get("availability_zone")):
                issues.append(
                    validation_issue(
                        node,
                        field="properties.availability_zone",
                        message="Subnet 가용영역 입력 필요",
                        suggested_action=f"{label}의 가용영역을 입력하세요.",
                    )
                )
        if (
            node_type == "aws.ec2.vpc"
            and _filled(props.get("cidr"))
            and not _valid_cidr(props.get("cidr"))
        ):
            issues.append(
                validation_issue(
                    node,
                    field="properties.cidr",
                    message="VPC CIDR 형식 오류",
                    suggested_action=f"{label}의 CIDR을 예: 10.0.0.0/16 형식으로 입력하세요.",
                )
            )

    return issues


def validation_issue(
    node: dict[str, Any],
    *,
    field: str,
    message: str,
    suggested_action: str,
) -> dict[str, Any]:
    return {
        "node_id": node.get("id"),
        "node_type": node.get("type"),
        "display_name": node_label(node),
        "severity": "error",
        "field": field,
        "message": message,
        "suggested_action": suggested_action,
    }


def _filled(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _edges_by_node(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source:
            out.setdefault(source, []).append(edge)
        if target:
            out.setdefault(target, []).append(edge)
    return out


def _valid_cidr(value: Any) -> bool:
    try:
        ip_network(str(value), strict=False)
    except ValueError:
        return False
    return True


def _subnet_in_vpc(subnet_cidr: Any, vpc_cidr: Any) -> bool:
    try:
        subnet = ip_network(str(subnet_cidr), strict=False)
        vpc = ip_network(str(vpc_cidr), strict=False)
    except ValueError:
        return False
    return subnet.subnet_of(vpc)
