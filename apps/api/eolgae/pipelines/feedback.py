"""AI 피드백 엔진 — Canvas → LLM → 구조화된 피드백.

1차 MVP: 4종 노드 (EC2 / ALB / RDS / S3) 기반의 보안/비용/HA/운영 평가.
RAG / eval framework / 캐싱 은 후속.
"""
import hashlib
import json
import logging
import re
import time
from collections.abc import Iterator
from typing import Any

from eolgae.schemas.feedback import (
    Category,
    FeedbackItem,
    FeedbackResponse,
    ReviewContext,
    Severity,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 AWS 클라우드 아키텍처 전문가입니다. 사용자가 설계한 AWS 인프라 캔버스를 검토하고 4가지 차원에서 이슈를 찾아 피드백을 제공합니다.

## 평가 차원

1. **security (보안)** — public 노출, 암호화 누락, SG 0.0.0.0/0, IAM 권한 과다 등
2. **cost (비용)** — over-provisioning, 비효율 패턴, 불필요한 NAT GW, Multi-AZ 과사용 등
3. **ha (고가용성)** — Single AZ, Auto Scaling 미설정, failover 부재, SPOF 등
4. **operations (운영성)** — 모니터링 누락, 하드코딩, 태그 부재, 백업 부재 등

## 엣지(연결) 의미 평가도 포함

캔버스의 각 엣지에는 `type` 필드가 있습니다. 5종 의미:

- `network` — 네트워크 트래픽 (예: ALB → EC2). SG ingress/egress rule 필요
- `depends_on` — 일반 의존성 (Terraform depends_on)
- `data_flow` — 데이터 흐름 (예: EC2 → S3). IAM policy / 권한 필요
- `route` — 라우팅 (예: Subnet → IGW). Route Table entry 필요
- `reference` — 단순 참조 (예: EC2 → IAM Role). iam_instance_profile 등

엣지 검토 시 다음을 피드백 항목으로 표면화:

- 엣지 type 과 source/target 노드 type 의 조합이 *어색하거나 모호* 한 경우 (예: S3 → RDS network 엣지는 의미 불명확)
- 엣지 type 이 *암시하는 선결 리소스가 누락* (예: `data_flow` 엣지 있는데 IAM Role 노드 없음, `network` 엣지인데 SG 노드 없음)
- 엣지의 properties (port_range / protocol) 가 비어 있고 *의미 추론 어려운* 경우
- 엣지가 *완전 누락* 된 경우 (예: ALB 와 EC2 가 둘 다 있는데 둘 사이 엣지 없음 → 트래픽 의도 불명)

엣지 관련 피드백은 `target_edge_id` 에 엣지 ID 명시 (노드 무관 시 `target_node_id` 는 null).

## 그룹 포함 관계 해석

각 노드는 `parent_group_id` 와 검토 보조 필드 `containment_path` 를 가질 수 있습니다.
`containment_path` 는 가장 가까운 그룹부터 바깥 그룹 순서입니다. 예: EC2 의
`containment_path = [Subnet, VPC]` 라면 해당 EC2 는 그 Subnet 안에 있고, 그
Subnet 은 VPC 안에 있습니다. 네트워크/보안/HA 검토 시 이 포함 관계를 우선
컨텍스트로 사용하세요.

## 출력 형식

JSON 만 출력. 다른 텍스트 (설명 / 마크다운 코드블록 등) 없이 순수 JSON.

```
{
  "items": [
    {
      "category": "security|cost|ha|operations",
      "severity": "critical|high|medium|low",
      "title": "짧은 제목 (한국어, 60자 이내)",
      "description": "상세 설명 (한국어, 왜 문제인지 + 영향)",
      "target_node_id": "관련 노드 ID 또는 null",
      "target_edge_id": "관련 엣지 ID 또는 null",
      "recommendation": "권장 조치 (한국어, 무엇을 어떻게)"
    }
  ],
  "summary": "전체 요약 (한국어, 2~3 문장)"
}
```

## 평가 원칙

- 한국어로 작성 (모든 텍스트 필드)
- AWS Well-Architected Framework 기반
- 4종 노드만 있는 단순한 캔버스라도 *깊이 있는* 분석 (단순 표면 분석 X)
- 빠진 컴포넌트 지적 가능 (예: "S3 backup 부재", "ALB 단일 인스턴스 backend 위험")
- 구조적 우선순위:
  - Critical: public 데이터 저장소, DB public 노출, RDS/EC2 보호 SG 부재처럼 즉시 사고로 이어질 수 있는 설계
  - High: 단일 AZ 웹/DB, ALB 뒤 단일 EC2, IAM 없이 S3 data_flow, 앱-DB network edge 보호 근거 부재
  - Medium: HTTP listener, 백업/버전관리/암호화/로그 정책 누락, 비용 비효율
  - Low: 태그/명명/운영 표준화, 명시성 개선, 장기 운영 편의성
- 보안/HA/운영성은 "리소스가 있다/없다"만 보지 말고 트래픽 경로, 장애 도메인, 권한 경계, 복구 가능성을 함께 판단
- 비용은 단순 절감보다 MVP 설계 의도와 낭비/과잉 HA/불필요한 NAT Gateway 같은 구조적 비용 리스크를 지적
- severity 분배: 모두 critical 이면 신뢰도 ↓, 의미있는 비율로
- 발견된 이슈가 없으면 items 빈 배열 + summary 에 긍정 평가
- target_node_id / target_edge_id 는 캔버스의 실제 id 값이어야 함 (없으면 null)
"""

USER_PROMPT_TEMPLATE = """다음 AWS 아키텍처 캔버스를 검토하세요:

## 사용자의 설계 의도 / 검토 기준

{review_context}

검토 기준이 비어 있거나 `unknown` 인 항목은 보수적으로 가정하되, summary 에
무엇을 가정했는지 짧게 밝히세요. 명시된 목적/환경/가용성/비용 성향은
severity 판단과 recommendation 우선순위에 반영하세요. 추가 질문이 필요하면
자동 수정안이나 대화형 절차로 확장하지 말고 summary 또는 item description 에
"추가 확인 필요" 로 남기세요.

## 캔버스 graph

```json
{canvas_json}
```

위 캔버스에 대한 피드백을 JSON 형식으로 출력하세요."""


def generate_feedback(
    graph: dict[str, Any],
    review_context: ReviewContext | None = None,
) -> FeedbackResponse:
    """캔버스 그래프 → LLM 단일 호출 → 구조화된 응답 (non-streaming)."""
    from eolgae.services.llm import get_llm

    review_graph = enrich_graph_with_containment(graph)
    canvas_json = json.dumps(review_graph, ensure_ascii=False, indent=2)
    llm = get_llm()
    logger.info(
        "feedback: provider=%s model=%s nodes=%d",
        llm.provider,
        llm.model,
        len(review_graph.get("nodes") or []),
    )

    t0 = time.monotonic()
    raw = llm.complete_json(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(
            canvas_json=canvas_json,
            review_context=format_review_context(review_context),
        ),
    )
    logger.info("feedback: LLM %.1fs / %d chars", time.monotonic() - t0, len(raw or ""))

    return parse_feedback(review_graph, raw)


def stream_feedback_raw(
    graph: dict[str, Any],
    review_context: ReviewContext | None = None,
) -> Iterator[str]:
    """LLM 응답을 chunk 별로 yield. caller 가 누적 후 parse 필요.

    nginx default 60s timeout 회피 — chunk 가 계속 흐르면 connection 유지됨.
    """
    from eolgae.services.llm import get_llm

    review_graph = enrich_graph_with_containment(graph)
    canvas_json = json.dumps(review_graph, ensure_ascii=False, indent=2)
    llm = get_llm()
    logger.info(
        "feedback.stream: provider=%s model=%s nodes=%d",
        llm.provider,
        llm.model,
        len(review_graph.get("nodes") or []),
    )
    yield from llm.complete_json_stream(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(
            canvas_json=canvas_json,
            review_context=format_review_context(review_context),
        ),
    )


def format_review_context(review_context: ReviewContext | None) -> str:
    """Prompt-friendly design intent block."""
    if review_context is None:
        return "- 미입력: 캔버스 구조만 기준으로 검토"

    data = review_context.model_dump()
    labels = {
        "purpose": "목적",
        "environment": "환경",
        "availability_target": "가용성 목표",
        "cost_posture": "비용 성향",
        "traffic_expectation": "예상 트래픽",
        "notes": "추가 메모",
    }
    lines: list[str] = []
    for key, label in labels.items():
        value = str(data.get(key) or "").strip()
        if not value:
            value = "unknown"
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def enrich_graph_with_containment(graph: dict[str, Any]) -> dict[str, Any]:
    """LLM 검토용 그래프에 parent group chain 을 명시적으로 주입.

    FE 저장값인 `parent_group_id` 는 노드 단일 필드라 LLM 이 전체 위계를
    추론하기 어렵다. 검토 입력에만 `containment_path` 를 추가해 VPC/Subnet
    컨텍스트를 놓치지 않게 한다. 원본 graph 는 변경하지 않는다.
    """
    nodes = list(graph.get("nodes") or [])
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}

    enriched_nodes: list[dict[str, Any]] = []
    for node in nodes:
        enriched = dict(node)
        path: list[dict[str, Any]] = []
        seen: set[str] = set()
        parent_id = node.get("parent_group_id")
        while parent_id and str(parent_id) not in seen:
            parent_key = str(parent_id)
            seen.add(parent_key)
            parent = node_by_id.get(parent_key)
            if not parent:
                break
            path.append(
                {
                    "id": parent.get("id"),
                    "type": parent.get("type"),
                    "display_name": parent.get("display_name") or "",
                }
            )
            parent_id = parent.get("parent_group_id")

        if path:
            enriched["containment_path"] = path
            enriched["nearest_group"] = path[0]
        enriched_nodes.append(enriched)

    return {**graph, "nodes": enriched_nodes}


def parse_feedback(graph: dict[str, Any], raw: str) -> FeedbackResponse:
    """누적된 LLM 응답 텍스트 → 구조화된 FeedbackResponse."""
    canvas_hash = _hash_graph(graph)
    parsed = _extract_json(raw)

    baseline_items = build_rule_based_feedback(graph)
    items_raw = parsed.get("items", [])
    items: list[FeedbackItem] = []
    items.extend(baseline_items)
    for idx, item in enumerate(items_raw):
        try:
            items.append(FeedbackItem(**item))
        except Exception as e:
            logger.warning(
                "feedback: item[%d] schema 위반 → skip: %s", idx, e
            )
            continue

    summary = parsed.get("summary", "")
    if baseline_items and not summary:
        summary = (
            "룰 기반 안전장치가 즉시 확인 가능한 구조 리스크를 먼저 표시했습니다. "
            "보안, 고가용성, 운영성 항목을 우선 정리한 뒤 재검토하세요."
        )
    return FeedbackResponse(
        items=items,
        summary=summary,
        canvas_hash=canvas_hash,
    )


def build_rule_based_feedback(graph: dict[str, Any]) -> list[FeedbackItem]:
    """Deterministic MVP quality floor for issues that must not be missed.

    LLM 은 설명의 깊이와 맥락 보강을 맡고, 이 룰들은 대표 샘플에서 반드시
    잡혀야 하는 보안/HA/운영성 이슈와 node/edge annotation 을 보장한다.
    """
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    by_type: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        by_type.setdefault(str(node.get("type") or ""), []).append(node)

    items: list[FeedbackItem] = []
    sg_ids = {
        str(node.get("id"))
        for node in by_type.get("aws.ec2.security_group", [])
    }
    iam_role_ids = {
        str(node.get("id"))
        for node in by_type.get("aws.iam.role", [])
    }
    compute_types = {"aws.ec2.instance", "aws.ec2.asg"}

    def add(
        *,
        category: Category,
        severity: Severity,
        title: str,
        description: str,
        recommendation: str,
        target_node_id: str | None = None,
        target_edge_id: str | None = None,
    ) -> None:
        items.append(
            FeedbackItem(
                category=category,
                severity=severity,
                title=title,
                description=description,
                target_node_id=target_node_id,
                target_edge_id=target_edge_id,
                recommendation=recommendation,
            )
        )

    for bucket in by_type.get("aws.s3.bucket", []):
        props = _props(bucket)
        node_id = _node_id(bucket)
        if props.get("public_access_block") is False:
            add(
                category="security",
                severity="critical",
                title="S3 public access 차단이 꺼져 있음",
                description=(
                    "버킷의 public access block 이 false 입니다. 정적 웹 호스팅처럼 "
                    "의도된 공개가 아니라면 객체 유출 사고로 바로 이어질 수 있습니다."
                ),
                recommendation=(
                    "기본값은 public access block=true 로 두고, 공개가 필요하면 CloudFront/OAC "
                    "또는 명시적 bucket policy 로 범위를 제한하세요."
                ),
                target_node_id=node_id,
            )
    for rds in by_type.get("aws.rds.db_instance", []):
        props = _props(rds)
        node_id = _node_id(rds)
        if props.get("publicly_accessible") is True or props.get("public_access") is True:
            add(
                category="security",
                severity="critical",
                title="RDS public 접근이 허용됨",
                description=(
                    "데이터베이스가 public subnet 또는 internet 경로에 노출되면 "
                    "인증 우회 취약점, credential 유출, 스캔 공격의 영향이 커집니다."
                ),
                recommendation=(
                    "RDS 는 private subnet 에 두고, 앱 계층 SG 에서만 필요한 "
                    "포트를 허용하세요."
                ),
                target_node_id=node_id,
            )
        if props.get("multi_az") is not True:
            add(
                category="ha",
                severity="high",
                title="RDS Multi-AZ가 비활성화됨",
                description=(
                    "단일 AZ RDS 는 AZ 장애, 호스트 장애, 유지보수 이벤트에서 "
                    "서비스 중단 시간이 길어질 수 있습니다."
                ),
                recommendation=(
                    "운영 DB 는 Multi-AZ 를 켜고 백업 보존 기간과 복구 절차를 "
                    "명시하세요."
                ),
                target_node_id=node_id,
            )
        if not _has_sg_association(node_id, edges, sg_ids):
            add(
                category="security",
                severity="critical",
                title="RDS 보호 Security Group 연결이 없음",
                description=(
                    "DB 노드에 명시적인 SG association 이 없어 어떤 앱 계층에서 "
                    "어떤 포트로 접근하는지 검토할 근거가 없습니다."
                ),
                recommendation=(
                    "RDS 전용 SG 를 만들고 EC2/ASG SG 에서 DB 포트만 허용하는 "
                    "network/reference edge 를 추가하세요."
                ),
                target_node_id=node_id,
            )

    alb_nodes = by_type.get("aws.ec2.alb", [])
    compute_nodes = [
        node
        for node in nodes
        if node.get("type") in compute_types
    ]
    for alb in alb_nodes:
        props = _props(alb)
        node_id = _node_id(alb)
        subnet_azs = _placement_azs(alb, nodes_by_id)
        if len(subnet_azs) < 2:
            add(
                category="ha",
                severity="high",
                title="ALB가 2개 이상 AZ에 걸쳐 있지 않음",
                description=(
                    "ALB 는 최소 두 가용영역의 subnet 에 걸쳐야 AZ 장애를 "
                    "흡수하고 AWS 권장 구성에 맞습니다."
                ),
                recommendation=(
                    "서로 다른 AZ 의 public subnet 두 개 이상에 ALB 를 배치하세요."
                ),
                target_node_id=node_id,
            )
        if not _has_sg_association(node_id, edges, sg_ids):
            add(
                category="security",
                severity="high",
                title="ALB Security Group 경계가 명시되지 않음",
                description=(
                    "인터넷 진입점인 ALB 에 SG association 이 없으면 inbound "
                    "80/443 과 backend egress 범위를 검토할 수 없습니다."
                ),
                recommendation=(
                    "ALB 전용 SG 를 만들고 공개 포트와 backend 대상 SG 만 "
                    "허용하도록 edge 를 추가하세요."
                ),
                target_node_id=node_id,
            )

    ec2_backend_count = sum(
        1 for node in compute_nodes if node.get("type") == "aws.ec2.instance"
    )
    if alb_nodes and ec2_backend_count == 1:
        add(
            category="ha",
            severity="high",
            title="ALB 뒤 backend가 단일 EC2로 보임",
            description=(
                "ALB 가 있어도 실제 backend 가 단일 EC2 라면 인스턴스 장애나 "
                "배포 중단을 흡수하지 못합니다."
            ),
            recommendation=(
                "ASG 를 사용하거나 최소 두 AZ 에 EC2 backend 를 분산하고 "
                "health check 기반으로 교체되게 구성하세요."
            ),
            target_node_id=_node_id(alb_nodes[0]),
        )

    for compute in compute_nodes:
        node_id = _node_id(compute)
        if not _has_sg_association(node_id, edges, sg_ids):
            add(
                category="security",
                severity="high",
                title="Compute 노드의 SG association이 없음",
                description=(
                    "EC2/ASG 에 SG 연결이 없으면 ALB, DB, S3 접근 경계를 "
                    "캔버스에서 검증할 수 없습니다."
                ),
                recommendation=(
                    "워크로드 전용 SG 를 만들고 ALB 또는 필요한 peer 에서만 "
                    "inbound 를 허용하세요."
                ),
                target_node_id=node_id,
            )

    for edge in edges:
        edge_id = str(edge.get("id") or "")
        source = nodes_by_id.get(str(edge.get("source")))
        target = nodes_by_id.get(str(edge.get("target")))
        if not source or not target:
            continue
        source_type = str(source.get("type") or "")
        target_type = str(target.get("type") or "")
        edge_type = str(edge.get("type") or "network")
        if edge_type == "data_flow" and "aws.s3.bucket" in {source_type, target_type}:
            if not _edge_touches_any(edge, iam_role_ids) and not iam_role_ids:
                add(
                    category="security",
                    severity="high",
                    title="S3 data_flow에 IAM Role 근거가 없음",
                    description=(
                        "S3 접근 흐름은 네트워크가 아니라 IAM 권한 문제입니다. "
                        "IAM Role/Policy 근거 없이 data_flow 만 있으면 최소 권한 "
                        "검토가 불가능합니다."
                    ),
                    recommendation=(
                        "EC2/ASG 에 IAM Role reference edge 를 추가하고 S3 "
                        "버킷/프리픽스 단위 최소 권한을 명시하세요."
                    ),
                    target_edge_id=edge_id,
                )
        if edge_type == "network" and "aws.rds.db_instance" in {source_type, target_type}:
            rds_id = _node_id(source if source_type == "aws.rds.db_instance" else target)
            if not _has_sg_association(rds_id, edges, sg_ids):
                add(
                    category="security",
                    severity="high",
                    title="DB network edge에 SG 경계가 없음",
                    description=(
                        "앱-DB network edge 는 포트와 source SG 제한이 핵심인데, "
                        "현재 캔버스에서는 DB 접근 경계를 확인할 수 없습니다."
                    ),
                    recommendation=(
                        "DB SG 와 앱 SG 를 추가하고 DB 포트만 허용되는 관계를 "
                        "edge 로 명시하세요."
                    ),
                    target_edge_id=edge_id,
                )

    return items


def _props(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties")
    return props if isinstance(props, dict) else {}


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or "")


def _has_sg_association(
    node_id: str,
    edges: list[dict[str, Any]],
    sg_ids: set[str],
) -> bool:
    if not node_id or not sg_ids:
        return False
    for edge in edges:
        if str(edge.get("type") or "network") not in {"network", "reference"}:
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source == node_id and target in sg_ids:
            return True
        if target == node_id and source in sg_ids:
            return True
    return False


def _edge_touches_any(edge: dict[str, Any], node_ids: set[str]) -> bool:
    return (
        str(edge.get("source") or "") in node_ids
        or str(edge.get("target") or "") in node_ids
    )


def _placement_azs(
    node: dict[str, Any],
    nodes_by_id: dict[str, dict[str, Any]],
) -> set[str]:
    azs: set[str] = set()
    parent_id = node.get("parent_group_id")
    vpc_id: str | None = None
    seen: set[str] = set()
    while parent_id and str(parent_id) not in seen:
        parent_key = str(parent_id)
        seen.add(parent_key)
        parent = nodes_by_id.get(parent_key)
        if not parent:
            break
        if parent.get("type") == "aws.ec2.subnet":
            az = _props(parent).get("availability_zone")
            if az:
                azs.add(str(az))
        if parent.get("type") == "aws.ec2.vpc":
            vpc_id = parent_key
        parent_id = parent.get("parent_group_id")

    if vpc_id:
        for candidate in nodes_by_id.values():
            if candidate.get("type") != "aws.ec2.subnet":
                continue
            if candidate.get("parent_group_id") != vpc_id:
                continue
            az = _props(candidate).get("availability_zone")
            if az:
                azs.add(str(az))
    return azs


def _hash_graph(graph: dict[str, Any]) -> str:
    """캔버스 그래프 hash (캐싱 키 — 1차 MVP 에선 사용 안 함, 후속용)."""
    canonical = json.dumps(graph, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\n?(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """LLM 응답에서 JSON 추출. 마크다운 코드 블록 / 앞뒤 텍스트 처리."""
    text = text.strip()

    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]

    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return {"items": [], "summary": "AI 응답 파싱 실패 — 다시 시도 부탁"}
