"""OpenTofu HCL generator from Canvas graph.

1차 MVP: 4 종 노드 (EC2 / ALB / RDS / S3) + 5 종 엣지 (network / depends_on /
data_flow / route / reference) 부분 지원.

엣지 매핑 정책:
- `depends_on`: Terraform `depends_on` meta-argument 로 직접 박음 (완전 자동)
- `network` / `data_flow` / `route` / `reference`: 노드 블록 아래 컨텍스트 주석으로
  의미 보존. SG / Subnet / IAM Role 등 *연결 대상 리소스 노드* 가 1차 MVP 4 종에
  포함되지 않아 완전 자동화 불가. 운영자가 주석을 보고 손으로 보완.

생성된 코드는 *시작점* 수준. 다만 캔버스 containment 로 확실히 추론 가능한
VPC/Subnet 참조는 자동 연결하고, 사용자 의도가 필요한 값은 validation 에서 막음.
"""
from typing import Any

from eolgae.pipelines.graph_model import (
    GenerationContext,
    display_ref,
    node_tf_ref,
    normalize_name,
)
from eolgae.pipelines.tofu_adapters.aws_resources import render_aws_resource


def generate_tofu(canvas_data: dict[str, Any]) -> str:
    """Generate OpenTofu HCL string from canvas dict.

    Args:
        canvas_data: dict with keys "graph" (with nodes/edges/groups) and "aws_account"
    """
    blocks: list[str] = []

    aws_account = canvas_data.get("aws_account") or {}
    region = aws_account.get("default_region", "ap-northeast-2")
    blocks.append(_provider_block(region))

    graph = canvas_data.get("graph") or {}
    system_tags = canvas_data.get("system_tags") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    ctx = GenerationContext(nodes)

    node_map: dict[str, tuple[str, str]] = {
        n["id"]: (normalize_name(n["id"]), n.get("type", ""))
        for n in nodes
        if n.get("id")
    }

    edges_by_source: dict[str, list[dict[str, Any]]] = {}
    edges_by_target: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        if "source" in e:
            edges_by_source.setdefault(e["source"], []).append(e)
        if "target" in e:
            edges_by_target.setdefault(e["target"], []).append(e)

    for node in nodes:
        node_id = node.get("id", "")
        incoming = edges_by_target.get(node_id, [])
        outgoing = edges_by_source.get(node_id, [])
        block = _node_to_tofu(node, incoming, outgoing, node_map, ctx, system_tags)
        if block:
            blocks.append(block)

    return "\n\n".join(blocks) + "\n"


def _provider_block(region: str) -> str:
    return f"""terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"
}}"""


def _node_to_tofu(
    node: dict[str, Any],
    incoming: list[dict[str, Any]],
    outgoing: list[dict[str, Any]],
    node_map: dict[str, tuple[str, str]],
    ctx: GenerationContext,
    system_tags: dict[str, str],
) -> str:
    node_type = node.get("type", "")
    node_id = node.get("id", "")
    props = node.get("properties") or {}

    tf_name = normalize_name(node_id)

    depends_on_block = _depends_on_block(incoming, node_map)
    edge_notes = _edge_notes(incoming, outgoing, node_map)
    parent_notes = _parent_notes(node, ctx)
    inferred = ctx.infer(node, [*incoming, *outgoing])

    body = render_aws_resource(
        node_type=node_type,
        tf_name=tf_name,
        props=props,
        depends_on_block=depends_on_block,
        inferred=inferred,
        system_tags=system_tags,
    )
    if not body:
        return ""

    notes = [*parent_notes, *edge_notes]
    if notes:
        return f"{body}\n\n# Canvas 컨텍스트 ({tf_name}):\n" + "\n".join(
            f"# - {n}" for n in notes
        )
    return body


def _parent_notes(node: dict[str, Any], ctx: GenerationContext) -> list[str]:
    ancestors = ctx.ancestors(node)
    if not ancestors:
        return []
    chain = " > ".join(
        f"{a.get('type', '')}:{normalize_name(a.get('id', ''))}" for a in ancestors
    )
    return [f"parent_group chain: {chain}"]


def _depends_on_block(
    incoming: list[dict[str, Any]],
    node_map: dict[str, tuple[str, str]],
) -> str:
    """`depends_on` 엣지의 source 노드들을 Terraform depends_on 리스트로 변환."""
    refs: list[str] = []
    for e in incoming:
        if e.get("type") != "depends_on":
            continue
        ref = node_tf_ref(e.get("source", ""), node_map)
        if ref:
            refs.append(ref)
    if not refs:
        return ""
    joined = ",\n    ".join(refs)
    return f"\n  depends_on = [\n    {joined},\n  ]"


def _edge_notes(
    incoming: list[dict[str, Any]],
    outgoing: list[dict[str, Any]],
    node_map: dict[str, tuple[str, str]],
) -> list[str]:
    """엣지 의미를 *.tf 주석으로 자연어 변환 (depends_on 외)."""
    notes: list[str] = []

    for e in incoming:
        etype = e.get("type", "network")
        if etype == "depends_on":
            continue
        source = e.get("source", "")
        source_name = display_ref(source, node_map)
        notes.append(_edge_note_for("incoming", etype, source_name, e.get("properties") or {}))

    for e in outgoing:
        etype = e.get("type", "network")
        if etype == "depends_on":
            continue
        target = e.get("target", "")
        target_name = display_ref(target, node_map)
        notes.append(_edge_note_for("outgoing", etype, target_name, e.get("properties") or {}))

    return notes


def _edge_note_for(
    direction: str,
    etype: str,
    other: str,
    props: dict[str, Any],
) -> str:
    """엣지 1건을 사람 읽기 좋은 1줄 주석으로 변환."""
    port = props.get("port_range") or ""
    proto = props.get("protocol") or ""
    label = props.get("label") or ""
    extras: list[str] = []
    if port:
        extras.append(f"port={port}")
    if proto:
        extras.append(f"protocol={proto}")
    if label:
        extras.append(f"label={label!r}")
    extra_str = f" ({', '.join(extras)})" if extras else ""

    arrow = "from" if direction == "incoming" else "to"

    descriptions = {
        "network": (
            f"network {arrow} {other}{extra_str} — Security Group rule 필요 "
            "(1차 MVP 4종에 SG 노드 미포함, 운영자 수동 보완)"
        ),
        "data_flow": (
            f"data_flow {arrow} {other}{extra_str} — IAM policy / 권한 필요 "
            "(IAM Role 노드 추가 + policy 연결 필요)"
        ),
        "route": (
            f"route {arrow} {other}{extra_str} — Route Table 연결 "
            "(Route Table과 IGW/NAT/Subnet route edge는 HCL로 자동 반영)"
        ),
        "reference": f"reference {arrow} {other}{extra_str} — 시각적 참조",
    }
    return descriptions.get(etype, f"{etype} {arrow} {other}{extra_str}")
