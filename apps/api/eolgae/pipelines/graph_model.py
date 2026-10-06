"""Normalized helpers for interpreting canvas graph structure."""
from __future__ import annotations

from typing import Any


NODE_TF_RESOURCE: dict[str, str] = {
    "aws.ec2.instance": "aws_instance",
    "aws.ec2.alb": "aws_lb",
    "aws.ec2.asg": "aws_autoscaling_group",
    "aws.rds.db_instance": "aws_db_instance",
    "aws.s3.bucket": "aws_s3_bucket",
    "aws.ec2.security_group": "aws_security_group",
    "aws.iam.role": "aws_iam_role",
    "aws.route53.record": "aws_route53_record",
    "aws.ec2.vpc": "aws_vpc",
    "aws.ec2.subnet": "aws_subnet",
    "aws.ec2.internet_gateway": "aws_internet_gateway",
    "aws.ec2.nat_gateway": "aws_nat_gateway",
    "aws.ec2.route_table": "aws_route_table",
}

ASSOCIATION_EDGE_TYPES = {"network", "reference"}


class InferredStructure:
    """Terraform refs inferred from canvas placement facts."""

    def __init__(
        self,
        *,
        vpc_ref: str | None,
        subnet_refs: list[str],
        security_group_refs: list[str],
        route_gateway_refs: list[tuple[str, str]] | None = None,
        route_subnet_refs: list[str] | None = None,
    ) -> None:
        self.vpc_ref = vpc_ref
        self.subnet_refs = subnet_refs
        self.security_group_refs = security_group_refs
        self.route_gateway_refs = route_gateway_refs or []
        self.route_subnet_refs = route_subnet_refs or []


class GenerationContext:
    """Canvas graph lookup helper for parent-group based Terraform refs."""

    def __init__(self, nodes: list[dict[str, Any]]) -> None:
        self.nodes_by_id = {n.get("id"): n for n in nodes if n.get("id")}

    def parent(self, node: dict[str, Any]) -> dict[str, Any] | None:
        parent_id = node.get("parent_group_id")
        if not parent_id:
            return None
        return self.nodes_by_id.get(parent_id)

    def ancestors(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = self.parent(node)
        while current and current.get("id") not in seen:
            seen.add(current["id"])
            out.append(current)
            current = self.parent(current)
        return out

    def nearest_ancestor_of_type(
        self,
        node: dict[str, Any],
        node_type: str,
    ) -> dict[str, Any] | None:
        for ancestor in self.ancestors(node):
            if ancestor.get("type") == node_type:
                return ancestor
        return None

    def tf_ref(self, node: dict[str, Any] | None) -> str | None:
        if not node:
            return None
        resource = NODE_TF_RESOURCE.get(node.get("type", ""))
        node_id = node.get("id")
        if not resource or not node_id:
            return None
        return f"{resource}.{normalize_name(node_id)}"

    def vpc_ref(self, node: dict[str, Any]) -> str | None:
        if node.get("type") == "aws.ec2.vpc":
            return self.tf_ref(node)
        return self.tf_ref(self.nearest_ancestor_of_type(node, "aws.ec2.vpc"))

    def subnet_ref(self, node: dict[str, Any]) -> str | None:
        if node.get("type") == "aws.ec2.subnet":
            return self.tf_ref(node)
        return self.tf_ref(self.nearest_ancestor_of_type(node, "aws.ec2.subnet"))

    def subnet_refs_for(self, node: dict[str, Any]) -> list[str]:
        direct = self.subnet_ref(node)
        if direct:
            return [direct]

        vpc = self.nearest_ancestor_of_type(node, "aws.ec2.vpc")
        if not vpc:
            return []

        refs: list[str] = []
        vpc_id = vpc.get("id")
        for candidate in self.nodes_by_id.values():
            if candidate.get("type") != "aws.ec2.subnet":
                continue
            if any(ancestor.get("id") == vpc_id for ancestor in self.ancestors(candidate)):
                ref = self.tf_ref(candidate)
                if ref:
                    refs.append(ref)
        return refs

    def security_group_refs_for(
        self,
        node: dict[str, Any],
        edges: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Return SG refs only when the canvas has an explicit association edge."""
        refs: list[str] = []
        node_id = node.get("id")
        if not node_id:
            return refs

        for edge in edges or []:
            if edge.get("type", "network") not in ASSOCIATION_EDGE_TYPES:
                continue
            source = edge.get("source")
            target = edge.get("target")
            if source == node_id:
                other_id = target
            elif target == node_id:
                other_id = source
            else:
                continue
            candidate = self.nodes_by_id.get(other_id)
            if not candidate or candidate.get("type") != "aws.ec2.security_group":
                continue
            ref = self.tf_ref(candidate)
            if ref and ref not in refs:
                refs.append(ref)
        return refs

    def route_refs_for(
        self,
        node: dict[str, Any],
        edges: list[dict[str, Any]] | None = None,
    ) -> tuple[list[tuple[str, str]], list[str]]:
        gateway_refs: list[tuple[str, str]] = []
        subnet_refs: list[str] = []
        node_id = node.get("id")
        if node.get("type") != "aws.ec2.route_table" or not node_id:
            return gateway_refs, subnet_refs

        for edge in edges or []:
            if edge.get("type") != "route":
                continue
            source = edge.get("source")
            target = edge.get("target")
            if source == node_id:
                other_id = target
            elif target == node_id:
                other_id = source
            else:
                continue
            candidate = self.nodes_by_id.get(other_id)
            if not candidate:
                continue
            ref = self.tf_ref(candidate)
            if not ref:
                continue
            candidate_type = candidate.get("type")
            if candidate_type == "aws.ec2.internet_gateway":
                gateway_refs.append(("gateway_id", ref))
            elif candidate_type == "aws.ec2.nat_gateway":
                gateway_refs.append(("nat_gateway_id", ref))
            elif candidate_type == "aws.ec2.subnet":
                subnet_refs.append(ref)
        return gateway_refs, subnet_refs

    def infer(
        self,
        node: dict[str, Any],
        edges: list[dict[str, Any]] | None = None,
    ) -> InferredStructure:
        vpc_ref = self.vpc_ref(node)
        if node.get("type") == "aws.ec2.security_group" and not vpc_ref:
            vpc_ref = self.associated_resource_vpc_ref(node, edges)
        route_gateway_refs, route_subnet_refs = self.route_refs_for(node, edges)
        return InferredStructure(
            vpc_ref=vpc_ref,
            subnet_refs=self.subnet_refs_for(node),
            security_group_refs=self.security_group_refs_for(node, edges),
            route_gateway_refs=route_gateway_refs,
            route_subnet_refs=route_subnet_refs,
        )

    def associated_resource_vpc_ref(
        self,
        node: dict[str, Any],
        edges: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Infer SG VPC from the resource it is explicitly attached to."""
        node_id = node.get("id")
        if not node_id:
            return None

        for edge in edges or []:
            if edge.get("type", "network") not in ASSOCIATION_EDGE_TYPES:
                continue
            source = edge.get("source")
            target = edge.get("target")
            if source == node_id:
                other_id = target
            elif target == node_id:
                other_id = source
            else:
                continue
            candidate = self.nodes_by_id.get(other_id)
            if not candidate or candidate.get("type") == "aws.ec2.security_group":
                continue
            ref = self.vpc_ref(candidate)
            if ref:
                return ref
        return None


def node_tf_ref(node_id: str, node_map: dict[str, tuple[str, str]]) -> str | None:
    entry = node_map.get(node_id)
    if not entry:
        return None
    tf_name, node_type = entry
    resource = NODE_TF_RESOURCE.get(node_type)
    if not resource:
        return None
    return f"{resource}.{tf_name}"


def display_ref(node_id: str, node_map: dict[str, tuple[str, str]]) -> str:
    return node_tf_ref(node_id, node_map) or node_id


def normalize_name(node_id: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in node_id)
    if safe and safe[0].isdigit():
        safe = "n_" + safe
    return safe or "unnamed"


def node_label(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    return (
        str(node.get("display_name") or props.get("name") or props.get("Name") or "")
        or normalize_name(str(node.get("id", "")))
    )
