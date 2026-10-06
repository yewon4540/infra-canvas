"""Canvas CRUD + OpenTofu 생성 endpoints."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from eolgae.auth.dependencies import get_current_user
from eolgae.config import settings
from eolgae.db import get_db
from eolgae.models.aws_connection import AwsConnection
from eolgae.models.canvas import Canvas
from eolgae.models.canvas_group import CanvasGroup
from eolgae.models.environment import Environment
from eolgae.models.group_aws_connection import GroupAwsConnection
from eolgae.models.target import Target
from eolgae.models.user import User
from eolgae.schemas.canvas import (
    CanvasCreate,
    CanvasDuplicateRequest,
    CanvasFragmentResponse,
    CanvasInsertFragmentRequest,
    CanvasFromTemplateRequest,
    CanvasResponse,
    CanvasTemplateResponse,
    CanvasUpdate,
)
from eolgae.services.aws_connections import (
    attach_or_create_connection,
    effective_aws_account,
    mark_connection_verified,
    serialize_aws_connection,
    sync_canvas_aws_account,
)
from eolgae.services.kubernetes_dry_run import kubernetes_dry_run_status
from eolgae.schemas.feedback import FeedbackRequest, FeedbackResponse
from eolgae.pipelines.feedback import (
    generate_feedback,
    parse_feedback,
    stream_feedback_raw,
)
from eolgae.pipelines.apply import generate_plan, serialize_plan_result
from eolgae.pipelines.kubernetes_generator import (
    generate_kubernetes_yaml,
    validate_kubernetes_canvas,
)
from eolgae.pipelines.tofu_generator import generate_tofu

router = APIRouter(prefix="/canvas", tags=["canvas"])

ROLE_ARN_RE = re.compile(r"^arn:aws:iam::(?P<account_id>\d{12}):role\/(?P<role_name>[\w+=,.@\-_/]+)$")


def _node(
    node_id: str,
    node_type: str,
    display_name: str,
    x: float,
    y: float,
    *,
    width: float | None = None,
    height: float | None = None,
    properties: dict | None = None,
    parent_group_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    node = {
        "id": node_id,
        "type": node_type,
        "display_name": display_name,
        "position": {"x": x, "y": y},
        "properties": properties or {},
        "metadata": metadata or {},
        "parent_group_id": parent_group_id,
    }
    if width is not None and height is not None:
        node["size"] = {"width": width, "height": height}
    return node


def _edge(edge_id: str, source: str, target: str, edge_type: str = "network") -> dict:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": edge_type,
        "properties": {},
        "metadata": {},
    }


def _template_graphs() -> dict[str, dict]:
    suffix = uuid4().hex[:8]
    return {
        "s3-private-bucket": {
            "name": "정적 파일 호스팅",
            "description": "Public access block이 켜진 S3 기반 파일 저장/호스팅 시작점",
            "graph": {
                "nodes": [
                    _node(
                        "tpl_s3_bucket",
                        "aws.s3.bucket",
                        "private-bucket",
                        160,
                        120,
                        properties={
                            "bucket_name": f"eolgae-s3-{suffix}",
                            "versioning": False,
                            "public_access_block": True,
                        },
                    )
                ],
                "edges": [],
                "groups": [],
            },
        },
        "web-alb-ec2-rds": {
            "name": "웹 서버 호스팅",
            "description": "Public ALB, app EC2, private RDS를 배치한 웹 서비스 아키텍처",
            "graph": {
                "nodes": [
                    _node(
                        "tpl_web_vpc",
                        "aws.ec2.vpc",
                        "web-vpc",
                        60,
                        60,
                        width=920,
                        height=560,
                        properties={"cidr": "10.10.0.0/16", "region": "ap-northeast-2"},
                    ),
                    _node(
                        "tpl_web_public_a",
                        "aws.ec2.subnet",
                        "public-a",
                        120,
                        150,
                        width=380,
                        height=180,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "cidr": "10.10.1.0/24",
                            "availability_zone": "ap-northeast-2a",
                            "type": "public",
                        },
                    ),
                    _node(
                        "tpl_web_public_c",
                        "aws.ec2.subnet",
                        "public-c",
                        540,
                        150,
                        width=380,
                        height=180,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "cidr": "10.10.2.0/24",
                            "availability_zone": "ap-northeast-2c",
                            "type": "public",
                        },
                    ),
                    _node(
                        "tpl_web_private_a",
                        "aws.ec2.subnet",
                        "private-a",
                        120,
                        380,
                        width=380,
                        height=180,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "cidr": "10.10.11.0/24",
                            "availability_zone": "ap-northeast-2a",
                            "type": "private",
                        },
                    ),
                    _node(
                        "tpl_web_private_c",
                        "aws.ec2.subnet",
                        "private-c",
                        540,
                        380,
                        width=380,
                        height=180,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "cidr": "10.10.12.0/24",
                            "availability_zone": "ap-northeast-2c",
                            "type": "private",
                        },
                    ),
                    _node(
                        "tpl_web_alb",
                        "aws.ec2.alb",
                        "public-alb",
                        330,
                        205,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "scheme": "internet-facing",
                            "listener_port": 80,
                            "security_group_ids": "",
                        },
                    ),
                    _node(
                        "tpl_web_ec2",
                        "aws.ec2.instance",
                        "app-server",
                        250,
                        430,
                        parent_group_id="tpl_web_private_a",
                        properties={
                            "instance_type": "t3.micro",
                            "ami_id": "",
                            "security_group_ids": "",
                        },
                    ),
                    _node(
                        "tpl_web_rds",
                        "aws.rds.db_instance",
                        "app-db",
                        670,
                        430,
                        parent_group_id="tpl_web_vpc",
                        properties={
                            "engine": "postgres",
                            "instance_class": "db.t3.micro",
                            "multi_az": True,
                            "security_group_ids": "",
                        },
                    ),
                ],
                "edges": [
                    _edge("tpl_edge_alb_ec2", "tpl_web_alb", "tpl_web_ec2", "network"),
                    _edge("tpl_edge_ec2_rds", "tpl_web_ec2", "tpl_web_rds", "data_flow"),
                ],
                "groups": [],
            },
        },
    }


def _fragment_graphs() -> dict[str, dict]:
    return {
        "vpc-basic-2az": {
            "name": "VPC 기본 구성 (2AZ)",
            "description": "VPC, public/private subnet 2AZ, IGW, public route table을 현재 캔버스에 추가",
            "graph": {
                "nodes": [
                    _node(
                        "frag_vpc",
                        "aws.ec2.vpc",
                        "main-vpc",
                        0,
                        0,
                        width=920,
                        height=560,
                        properties={"cidr": "10.20.0.0/16", "region": "ap-northeast-2"},
                    ),
                    _node(
                        "frag_public_a",
                        "aws.ec2.subnet",
                        "public-a",
                        60,
                        110,
                        width=380,
                        height=170,
                        parent_group_id="frag_vpc",
                        properties={
                            "cidr": "10.20.1.0/24",
                            "availability_zone": "ap-northeast-2a",
                            "type": "public",
                        },
                    ),
                    _node(
                        "frag_public_c",
                        "aws.ec2.subnet",
                        "public-c",
                        480,
                        110,
                        width=380,
                        height=170,
                        parent_group_id="frag_vpc",
                        properties={
                            "cidr": "10.20.2.0/24",
                            "availability_zone": "ap-northeast-2c",
                            "type": "public",
                        },
                    ),
                    _node(
                        "frag_private_a",
                        "aws.ec2.subnet",
                        "private-a",
                        60,
                        330,
                        width=380,
                        height=170,
                        parent_group_id="frag_vpc",
                        properties={
                            "cidr": "10.20.11.0/24",
                            "availability_zone": "ap-northeast-2a",
                            "type": "private",
                        },
                    ),
                    _node(
                        "frag_private_c",
                        "aws.ec2.subnet",
                        "private-c",
                        480,
                        330,
                        width=380,
                        height=170,
                        parent_group_id="frag_vpc",
                        properties={
                            "cidr": "10.20.12.0/24",
                            "availability_zone": "ap-northeast-2c",
                            "type": "private",
                        },
                    ),
                    _node(
                        "frag_igw",
                        "aws.ec2.internet_gateway",
                        "internet-gateway",
                        120,
                        30,
                        parent_group_id="frag_vpc",
                        properties={},
                    ),
                    _node(
                        "frag_public_rt",
                        "aws.ec2.route_table",
                        "public-route-table",
                        560,
                        30,
                        parent_group_id="frag_vpc",
                        properties={
                            "routes": [
                                {
                                    "cidr_block": "0.0.0.0/0",
                                    "target": "internet_gateway",
                                }
                            ]
                        },
                    ),
                ],
                "edges": [
                    _edge("frag_edge_vpc_igw", "frag_vpc", "frag_igw", "reference"),
                    _edge("frag_edge_rt_igw", "frag_public_rt", "frag_igw", "route"),
                    _edge("frag_edge_rt_public_a", "frag_public_rt", "frag_public_a", "route"),
                    _edge("frag_edge_rt_public_c", "frag_public_rt", "frag_public_c", "route"),
                ],
                "groups": [],
            },
        }
    }


class AwsBootstrapRequest(BaseModel):
    account_id: str
    region: str = "ap-northeast-2"


class AwsRoleArnRequest(BaseModel):
    role_arn: str


class AwsVerifyResponse(BaseModel):
    ok: bool
    status: str
    message: str
    assumed_arn: str | None = None


def _get_canvas_for_user(db: Session, canvas_id: UUID, user: User) -> Canvas:
    """캔버스 조회 + owner 격리. 레거시(owner_id NULL)는 첫 접근자가 자동 claim.

    - 없음 → 404
    - owner_id NULL → 자동 claim (owner_id=user.id, commit)
    - owner_id == user.id → OK
    - 그 외 → 403
    """
    canvas = db.get(Canvas, canvas_id)
    if canvas is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canvas not found",
        )
    if canvas.owner_id is None:
        canvas.owner_id = user.id
        db.commit()
        db.refresh(canvas)
    elif canvas.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="다른 사용자의 캔버스",
        )
    return canvas


def _template_text() -> str:
    here = Path(__file__).resolve()
    for parent in here.parents:
        path = parent / "infrastructure" / "cross-account-role.yaml"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise RuntimeError("cross-account-role.yaml template not found")


def _quick_create_url(
    *,
    region: str,
    external_id: str,
    source_account_id: str,
    template_url: str,
) -> str | None:
    if not template_url or not source_account_id:
        return None
    from urllib.parse import urlencode

    params = urlencode(
        {
            "templateURL": template_url,
            "stackName": "IaCPlanRoleStack",
            "param_ExternalId": external_id,
            "param_SourceAccountId": source_account_id,
            "param_SourcePrincipalName": "IaC_user",
        }
    )
    return (
        f"https://console.aws.amazon.com/cloudformation/home?region={region}"
        f"#/stacks/quickcreate?{params}"
    )


def _aws_account_binding(db: Session, canvas: Canvas) -> dict:
    return effective_aws_account(db, canvas)


def _connection_for_canvas(
    db: Session,
    *,
    canvas: Canvas,
    user: User,
    binding: dict | None = None,
) -> AwsConnection | None:
    if canvas.aws_connection_id:
        connection = db.get(AwsConnection, canvas.aws_connection_id)
        if connection is not None:
            return connection
    binding = binding or dict(canvas.aws_account or {})
    account_id = binding.get("account_id")
    external_id = binding.get("external_id")
    if not account_id or not external_id:
        return None
    connection = attach_or_create_connection(
        db,
        canvas=canvas,
        user=user,
        account_id=account_id,
        region=binding.get("default_region") or "ap-northeast-2",
    )
    connection.external_id = external_id
    connection.role_arn = binding.get("role_arn")
    connection.binding_status = binding.get("binding_status") or "pending_role"
    connection.default_tags = binding.get("default_tags") or {}
    connection.assumed_arn = binding.get("assumed_arn")
    sync_canvas_aws_account(canvas, connection)
    return connection


def _connection_snapshot(
    db: Session,
    *,
    user: User,
    aws_connection_id: UUID | None,
) -> dict | None:
    if not aws_connection_id:
        return None
    connection = db.get(AwsConnection, aws_connection_id)
    if connection is None or connection.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사용할 수 없는 AWS 연결",
        )
    return serialize_aws_connection(connection)


def _system_tags_for_canvas(db: Session, canvas: Canvas) -> dict[str, str]:
    tags = {
        "ManagedBy": "Eolgae",
        "EolgaeCanvasId": str(canvas.id),
    }
    if canvas.name:
        tags["EolgaeCanvasName"] = canvas.name
    if canvas.group_id:
        group = db.get(CanvasGroup, canvas.group_id)
        if group is not None:
            tags["EolgaeProjectGroup"] = group.slug
    if canvas.environment_id:
        environment = db.get(Environment, canvas.environment_id)
        if environment is not None:
            tags["EolgaeEnvironment"] = environment.slug
    return tags


def _owned_group_or_none(
    db: Session,
    *,
    user: User,
    group_id: UUID | None,
) -> CanvasGroup | None:
    if group_id is None:
        return None
    group = db.get(CanvasGroup, group_id)
    if group is None or group.owner_id != user.id or group.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사용할 수 없는 Project Group",
        )
    return group


def _owned_environment_or_none(
    db: Session,
    *,
    user: User,
    environment_id: UUID | None,
) -> Environment | None:
    if environment_id is None:
        return None
    environment = db.get(Environment, environment_id)
    if environment is None or environment.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사용할 수 없는 Environment",
        )
    return environment


def _default_connection_for_group(
    db: Session,
    group: CanvasGroup | None,
) -> UUID | None:
    if group is None:
        return None
    link = db.scalar(
        select(GroupAwsConnection).where(
            GroupAwsConnection.group_id == group.id,
            GroupAwsConnection.is_default.is_(True),
        )
    )
    return link.aws_connection_id if link else None


def _resolve_canvas_context(
    db: Session,
    *,
    user: User,
    group_id: UUID | None,
    environment_id: UUID | None,
    aws_connection_id: UUID | None,
    use_default_aws_connection: bool = True,
) -> tuple[UUID | None, UUID | None, UUID | None, dict | None]:
    group = _owned_group_or_none(db, user=user, group_id=group_id)
    if environment_id is None and group is not None:
        environment_id = group.default_environment_id
    _owned_environment_or_none(db, user=user, environment_id=environment_id)
    if aws_connection_id is None and use_default_aws_connection:
        aws_connection_id = _default_connection_for_group(db, group)
    aws_account = _connection_snapshot(
        db,
        user=user,
        aws_connection_id=aws_connection_id,
    )
    return (
        group.id if group else None,
        environment_id,
        aws_connection_id,
        aws_account,
    )


def _owned_target_or_none(
    db: Session,
    *,
    user: User,
    target_id: UUID | None,
    expected_kind: str | None = None,
) -> Target | None:
    if target_id is None:
        return None
    target = db.get(Target, target_id)
    if (
        target is None
        or target.owner_id != user.id
        or target.deleted_at is not None
        or target.archived_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사용할 수 없는 Target",
        )
    if expected_kind and target.kind != expected_kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{expected_kind} Target만 사용할 수 있습니다",
        )
    return target


def _design_graph_copy(graph: dict) -> dict:
    copied = json.loads(json.dumps(graph or {"nodes": [], "edges": [], "groups": []}))
    for node in copied.get("nodes", []):
        node.pop("aws_binding", None)
    for group in copied.get("groups", []):
        group.pop("aws_binding", None)
    copied.setdefault("nodes", [])
    copied.setdefault("edges", [])
    copied.setdefault("groups", [])
    return copied


def _insert_fragment_graph(base_graph: dict, fragment_graph: dict, *, x: float, y: float) -> dict:
    graph = _design_graph_copy(base_graph)
    fragment = _design_graph_copy(fragment_graph)
    existing_ids = {
        item.get("id")
        for item in [
            *graph.get("nodes", []),
            *graph.get("edges", []),
            *graph.get("groups", []),
        ]
        if item.get("id")
    }
    prefix = f"frag_{uuid4().hex[:8]}_"
    id_map: dict[str, str] = {}

    for collection in ("nodes", "edges", "groups"):
        for item in fragment.get(collection, []):
            old_id = item.get("id")
            if not old_id:
                continue
            new_id = f"{prefix}{old_id}"
            while new_id in existing_ids:
                new_id = f"{prefix}{uuid4().hex[:4]}_{old_id}"
            id_map[old_id] = new_id
            existing_ids.add(new_id)
            item["id"] = new_id

    for node in fragment.get("nodes", []):
        position = node.setdefault("position", {"x": 0, "y": 0})
        position["x"] = float(position.get("x") or 0) + x
        position["y"] = float(position.get("y") or 0) + y
        parent_id = node.get("parent_group_id")
        if parent_id:
            node["parent_group_id"] = id_map.get(parent_id, parent_id)

    for group in fragment.get("groups", []):
        position = group.setdefault("position", {"x": 0, "y": 0})
        position["x"] = float(position.get("x") or 0) + x
        position["y"] = float(position.get("y") or 0) + y
        parent_id = group.get("parent_group_id")
        if parent_id:
            group["parent_group_id"] = id_map.get(parent_id, parent_id)
        group["contained_node_ids"] = [
            id_map.get(node_id, node_id)
            for node_id in group.get("contained_node_ids", [])
        ]

    for edge in fragment.get("edges", []):
        edge["source"] = id_map.get(edge.get("source"), edge.get("source"))
        edge["target"] = id_map.get(edge.get("target"), edge.get("target"))

    graph["nodes"].extend(fragment.get("nodes", []))
    graph["edges"].extend(fragment.get("edges", []))
    graph["groups"].extend(fragment.get("groups", []))
    return graph


@router.get("", response_model=list[CanvasResponse])
def list_canvases(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Canvas]:
    """활성 캔버스 목록 — 본인 소유 + 레거시(owner 미지정). 최근 수정순. 휴지통 제외."""
    canvases = db.scalars(
        select(Canvas)
        .where(
            Canvas.deleted_at.is_(None),
            (Canvas.owner_id == user.id) | (Canvas.owner_id.is_(None)),
        )
        .order_by(Canvas.updated_at.desc())
    ).all()
    return list(canvases)


@router.get("/fragments", response_model=list[CanvasFragmentResponse])
def list_canvas_fragments(
    user: User = Depends(get_current_user),
) -> list[CanvasFragmentResponse]:
    """Reusable graph fragments that can be inserted into an existing canvas."""
    _ = user
    fragments = _fragment_graphs()
    return [
        CanvasFragmentResponse(
            id=fragment_id,
            name=fragment["name"],
            description=fragment["description"],
            node_count=len(fragment["graph"]["nodes"]),
            edge_count=len(fragment["graph"]["edges"]),
        )
        for fragment_id, fragment in fragments.items()
    ]


@router.get("/templates", response_model=list[CanvasTemplateResponse])
def list_canvas_templates(
    user: User = Depends(get_current_user),
) -> list[CanvasTemplateResponse]:
    """Built-in canvas templates. 사용자 정의 템플릿 저장은 후속 범위."""
    _ = user
    templates = _template_graphs()
    return [
        CanvasTemplateResponse(
            id=template_id,
            name=template["name"],
            description=template["description"],
            node_count=len(template["graph"]["nodes"]),
            edge_count=len(template["graph"]["edges"]),
        )
        for template_id, template in templates.items()
    ]


@router.post(
    "/from-template",
    response_model=CanvasResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_canvas_from_template(
    payload: CanvasFromTemplateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    templates = _template_graphs()
    template = templates.get(payload.template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canvas template not found",
        )

    canvas = Canvas(
        name=(payload.name or template["name"]).strip() or template["name"],
        description=template["description"],
        schema_version="0.1.0",
        state="design",
        canvas_kind="aws",
        graph=_design_graph_copy(template["graph"]),
        owner_id=user.id,
    )
    group_id, environment_id, connection_id, aws_account = _resolve_canvas_context(
        db,
        user=user,
        group_id=payload.group_id,
        environment_id=payload.environment_id,
        aws_connection_id=payload.aws_connection_id,
    )
    canvas.group_id = group_id
    canvas.environment_id = environment_id
    canvas.aws_connection_id = connection_id
    canvas.aws_account = aws_account
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.post(
    "/{canvas_id}/fragments",
    response_model=CanvasResponse,
    status_code=status.HTTP_201_CREATED,
)
def insert_canvas_fragment(
    canvas_id: UUID,
    payload: CanvasInsertFragmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    canvas = _get_canvas_for_user(db, canvas_id, user)
    fragments = _fragment_graphs()
    fragment = fragments.get(payload.fragment_id)
    if fragment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canvas fragment not found",
        )

    canvas.graph = _insert_fragment_graph(
        canvas.graph or {},
        fragment["graph"],
        x=payload.x,
        y=payload.y,
    )
    canvas.state = "design"
    db.commit()
    db.refresh(canvas)
    return canvas


@router.get("/trash", response_model=list[CanvasResponse])
def list_trash(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Canvas]:
    """휴지통 — soft delete 된 본인 캔버스 + 레거시. 삭제 시각 역순."""
    canvases = db.scalars(
        select(Canvas)
        .where(
            Canvas.deleted_at.is_not(None),
            (Canvas.owner_id == user.id) | (Canvas.owner_id.is_(None)),
        )
        .order_by(Canvas.deleted_at.desc())
    ).all()
    return list(canvases)


@router.post("", response_model=CanvasResponse, status_code=status.HTTP_201_CREATED)
def create_canvas(
    payload: CanvasCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    requested_aws_connection_id = (
        payload.aws_connection_id if payload.canvas_kind == "aws" else None
    )
    group_id, environment_id, connection_id, aws_account = _resolve_canvas_context(
        db,
        user=user,
        group_id=payload.group_id,
        environment_id=payload.environment_id,
        aws_connection_id=requested_aws_connection_id,
        use_default_aws_connection=payload.canvas_kind == "aws",
    )
    if payload.aws_account and connection_id is None:
        aws_account = payload.aws_account.model_dump()
    target = _owned_target_or_none(
        db,
        user=user,
        target_id=payload.target_id,
        expected_kind="kubernetes_cluster" if payload.canvas_kind == "kubernetes" else None,
    )
    if payload.canvas_kind == "aws":
        target = None
    if payload.canvas_kind == "kubernetes":
        connection_id = None
        aws_account = None

    canvas = Canvas(
        name=payload.name,
        description=payload.description,
        schema_version=payload.schema_version,
        state=payload.state,
        canvas_kind=payload.canvas_kind,
        graph=payload.graph.model_dump(),
        aws_connection_id=connection_id,
        aws_account=aws_account,
        owner_id=user.id,
        group_id=group_id,
        environment_id=environment_id,
        target_id=target.id if target else None,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.post(
    "/{canvas_id}/duplicate",
    response_model=CanvasResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_canvas(
    canvas_id: UUID,
    payload: CanvasDuplicateRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    source = _get_canvas_for_user(db, canvas_id, user)
    requested_name = (payload.name if payload else None) or f"{source.name} Copy"
    canvas = Canvas(
        name=requested_name.strip() or f"{source.name} Copy",
        description=source.description,
        schema_version=source.schema_version,
        state="design",
        canvas_kind=getattr(source, "canvas_kind", "aws") or "aws",
        graph=_design_graph_copy(source.graph),
        aws_connection_id=source.aws_connection_id,
        aws_account=dict(source.aws_account) if source.aws_account else None,
        owner_id=user.id,
        group_id=source.group_id,
        environment_id=source.environment_id,
        target_id=getattr(source, "target_id", None),
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.get("/{canvas_id}", response_model=CanvasResponse)
def get_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    return _get_canvas_for_user(db, canvas_id, user)


@router.put("/{canvas_id}", response_model=CanvasResponse)
def update_canvas(
    canvas_id: UUID,
    payload: CanvasUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    canvas = _get_canvas_for_user(db, canvas_id, user)
    update_data = payload.model_dump(exclude_unset=True)
    if "aws_connection_id" in update_data:
        connection_id = update_data["aws_connection_id"]
    else:
        connection_id = None
    if "aws_connection_id" in update_data and connection_id:
        connection = db.get(AwsConnection, connection_id)
        if connection is None or connection.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="사용할 수 없는 AWS 연결",
            )
        update_data["aws_account"] = serialize_aws_connection(connection)
    elif "aws_connection_id" in update_data:
        update_data["aws_account"] = None
    if "group_id" in update_data:
        _owned_group_or_none(db, user=user, group_id=update_data["group_id"])
    if "environment_id" in update_data:
        _owned_environment_or_none(
            db,
            user=user,
            environment_id=update_data["environment_id"],
        )
    if "target_id" in update_data:
        canvas_kind = update_data.get("canvas_kind") or canvas.canvas_kind
        if canvas_kind == "aws":
            update_data["target_id"] = None
        else:
            target = _owned_target_or_none(
                db,
                user=user,
                target_id=update_data["target_id"],
                expected_kind=(
                    "kubernetes_cluster" if canvas_kind == "kubernetes" else None
                ),
            )
            update_data["target_id"] = target.id if target else None
    for key, value in update_data.items():
        setattr(canvas, key, value)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.delete("/{canvas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """캔버스 soft delete — `deleted_at = NOW()` 만 채움. 행은 휴지통에 남음.

    복구: `POST /canvas/{id}/restore`
    영구 삭제: `DELETE /canvas/{id}/permanent` (휴지통에서만 가능)
    """
    canvas = _get_canvas_for_user(db, canvas_id, user)
    if canvas.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 휴지통에 있는 캔버스. /permanent 로 영구 삭제 가능",
        )
    canvas.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{canvas_id}/restore", response_model=CanvasResponse)
def restore_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Canvas:
    """휴지통의 캔버스 복구 — `deleted_at = NULL`."""
    canvas = _get_canvas_for_user(db, canvas_id, user)
    if canvas.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 활성 상태인 캔버스",
        )
    canvas.deleted_at = None
    db.commit()
    db.refresh(canvas)
    return canvas


@router.delete("/{canvas_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanent_delete_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """캔버스 영구 삭제 (hard delete) — 휴지통에 있는 캔버스만 허용. 복구 불가."""
    canvas = _get_canvas_for_user(db, canvas_id, user)
    if canvas.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="휴지통에 없는 캔버스는 영구 삭제 불가. 먼저 DELETE /canvas/{id}",
        )
    db.delete(canvas)
    db.commit()


@router.post("/{canvas_id}/generate-tofu")
def generate_tofu_for_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """캔버스 → OpenTofu HCL 생성 (1차 MVP — 4종 노드만 지원)."""
    canvas = _get_canvas_for_user(db, canvas_id, user)

    canvas_dict = {
        "graph": canvas.graph,
        "aws_account": canvas.aws_account,
        "system_tags": _system_tags_for_canvas(db, canvas),
    }
    tf_string = generate_tofu(canvas_dict)
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (canvas.name or "canvas")
    )
    return {"tf": tf_string, "filename": f"{safe_name}.tf"}


@router.post("/{canvas_id}/generate-kubernetes-yaml")
def generate_kubernetes_yaml_for_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """캔버스 Kubernetes 노드 → multi-document manifest YAML 생성."""
    canvas = _get_canvas_for_user(db, canvas_id, user)

    yaml_string = generate_kubernetes_yaml({"graph": canvas.graph})
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (canvas.name or "canvas")
    )
    return {"yaml": yaml_string, "filename": f"{safe_name}.k8s.yaml"}


@router.post("/{canvas_id}/validate-kubernetes")
def validate_kubernetes_for_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Kubernetes manifest validation before cluster-side dry-run/apply."""
    canvas = _get_canvas_for_user(db, canvas_id, user)
    if canvas.canvas_kind != "kubernetes":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kubernetes Canvas만 검증할 수 있습니다",
        )
    result = validate_kubernetes_canvas({"graph": canvas.graph})
    result["target_id"] = str(canvas.target_id) if canvas.target_id else None
    target = _owned_target_or_none(
        db,
        user=user,
        target_id=canvas.target_id,
        expected_kind="kubernetes_cluster",
    )
    result["dry_run"] = kubernetes_dry_run_status(
        validation_result=result,
        target=target,
    )
    return result


@router.post("/{canvas_id}/aws/bootstrap")
def bootstrap_aws_account(
    canvas_id: UUID,
    payload: AwsBootstrapRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Cross-account IAM Role 온보딩 시작.

    1차 구현: 캔버스 `aws_account` JSON 에 account_id / external_id / status 저장.
    """
    if not re.fullmatch(r"\d{12}", payload.account_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AWS 계정 ID 는 12자리 숫자여야 함",
        )

    canvas = _get_canvas_for_user(db, canvas_id, user)
    connection = attach_or_create_connection(
        db,
        canvas=canvas,
        user=user,
        account_id=payload.account_id,
        region=payload.region,
    )
    external_id = connection.external_id
    source_account_id = settings.eolgae_aws_account_id or ""
    template = _template_text()
    quick_url = _quick_create_url(
        region=payload.region,
        external_id=external_id,
        source_account_id=source_account_id,
        template_url=settings.cfn_template_url,
    )

    sync_canvas_aws_account(canvas, connection)
    db.commit()
    db.refresh(canvas)
    return {
        "account_id": connection.account_id,
        "region": connection.default_region,
        "external_id": external_id,
        "eolgae_account_id": settings.eolgae_aws_account_id,
        "role_arn": connection.role_arn,
        "binding_status": connection.binding_status,
        "cloudformation_template": template,
        "cloudformation_quick_create_url": quick_url,
    }


@router.put("/{canvas_id}/aws/role")
def save_aws_role_arn(
    canvas_id: UUID,
    payload: AwsRoleArnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """사용자가 CloudFormation Output 의 Role ARN 을 붙여넣으면 저장."""
    match = ROLE_ARN_RE.fullmatch(payload.role_arn.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role ARN 형식이 올바르지 않음",
        )

    canvas = _get_canvas_for_user(db, canvas_id, user)
    binding = _aws_account_binding(db, canvas)
    account_id = binding.get("account_id")
    role_account_id = match.group("account_id")
    if account_id and account_id != role_account_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 의 account_id 가 온보딩한 AWS 계정 ID 와 다름",
        )

    connection = _connection_for_canvas(db, canvas=canvas, user=user, binding=binding)
    if connection is None:
        connection = attach_or_create_connection(
            db,
            canvas=canvas,
            user=user,
            account_id=account_id or role_account_id,
            region=binding.get("default_region") or "ap-northeast-2",
        )
    connection.role_arn = payload.role_arn.strip()
    connection.binding_status = "role_saved"
    sync_canvas_aws_account(canvas, connection)
    db.commit()
    db.refresh(canvas)
    return serialize_aws_connection(connection)


@router.post("/{canvas_id}/aws/verify", response_model=AwsVerifyResponse)
def verify_aws_role(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AwsVerifyResponse:
    """STS AssumeRole 검증.

    boto3 credential 이 없는 local dev 에선 실패 메시지만 반환. 성공 시 verified 저장.
    """
    canvas = _get_canvas_for_user(db, canvas_id, user)
    binding = _aws_account_binding(db, canvas)
    role_arn = binding.get("role_arn")
    external_id = binding.get("external_id")
    account_id = binding.get("account_id")
    if not role_arn or not external_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role ARN 과 External ID 가 먼저 필요",
        )

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except Exception as e:
        return AwsVerifyResponse(
            ok=False,
            status="verify_unavailable",
            message=f"boto3 로드 실패: {e}",
        )

    try:
        sts = boto3.client("sts")
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"eolgae-verify-{canvas.id}",
            ExternalId=external_id,
            DurationSeconds=900,
        )
        creds = assumed["Credentials"]
        assumed_sts = boto3.client(
            "sts",
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
        identity = assumed_sts.get_caller_identity()
        assumed_account_id = identity.get("Account")
        assumed_arn = identity.get("Arn")
        if account_id and assumed_account_id != account_id:
            raise RuntimeError(
                f"AssumeRole account mismatch: expected={account_id}, got={assumed_account_id}"
            )
    except (BotoCoreError, ClientError, RuntimeError) as e:
        connection = _connection_for_canvas(db, canvas=canvas, user=user, binding=binding)
        if connection is not None:
            connection.binding_status = "verify_failed"
            sync_canvas_aws_account(canvas, connection)
        else:
            canvas.aws_account = {**binding, "binding_status": "verify_failed"}
        db.commit()
        return AwsVerifyResponse(
            ok=False,
            status="verify_failed",
            message=str(e),
        )

    connection = _connection_for_canvas(db, canvas=canvas, user=user, binding=binding)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AWS 연결 정보를 찾을 수 없음",
        )
    mark_connection_verified(
        canvas=canvas,
        connection=connection,
        assumed_arn=assumed_arn,
    )
    db.commit()
    return AwsVerifyResponse(
        ok=True,
        status="verified",
        message="AWS 계정 연결 검증 완료",
        assumed_arn=assumed_arn,
    )


@router.post("/{canvas_id}/plan")
def plan_canvas(
    canvas_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """캔버스 → .tf → tofu init/plan 동기 실행 (1차 PoC).

    한계 ([[018]] 진입 단계):
    - Cross-account AssumeRole 미적용 — 호스트 default credentials 사용
    - State backend local — 다회 호출 state 누적 안 됨
    - 동기 호출 — 큰 캔버스는 timeout 가능
    - apply 미실행 (plan 까지만)
    """
    canvas = _get_canvas_for_user(db, canvas_id, user)

    canvas_dict = {
        "graph": canvas.graph,
        "aws_account": canvas.aws_account,
    }
    result = generate_plan(canvas_dict)
    return serialize_plan_result(result)


@router.post("/{canvas_id}/feedback", response_model=FeedbackResponse)
def request_canvas_feedback(
    canvas_id: UUID,
    payload: FeedbackRequest | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """캔버스 → AI 피드백 (보안/비용/HA/운영 4 차원).

    1차 MVP: 4종 노드 (EC2/ALB/RDS/S3) 기반.
    LLM provider: ANTHROPIC_API_KEY 우선, 없으면 OPENAI_API_KEY.
    """
    canvas = _get_canvas_for_user(db, canvas_id, user)

    graph = canvas.graph or {}
    nodes = graph.get("nodes") or []
    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="캔버스가 비어있음 — 노드를 추가한 후 다시 시도",
        )

    try:
        return generate_feedback(graph, payload.review_context if payload else None)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 피드백 생성 실패: {e}",
        )


def _sse(event_type: str, payload: dict) -> str:
    """SSE event 포맷 — data: {json}\\n\\n"""
    body = json.dumps({"type": event_type, **payload}, ensure_ascii=False)
    return f"data: {body}\n\n"


@router.post("/{canvas_id}/feedback/stream")
def stream_canvas_feedback(
    canvas_id: UUID,
    payload: FeedbackRequest | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """캔버스 → AI 피드백 (SSE 스트리밍).

    이벤트 종류:
    - `{"type":"delta","content":"..."}` — LLM 텍스트 청크
    - `{"type":"complete","items":[...],"summary":"...","canvas_hash":"..."}` — 최종 파싱 결과
    - `{"type":"error","message":"..."}` — 에러 발생 시
    """
    canvas = _get_canvas_for_user(db, canvas_id, user)

    graph = canvas.graph or {}
    nodes = graph.get("nodes") or []
    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="캔버스가 비어있음 — 노드를 추가한 후 다시 시도",
        )

    def generate():
        accumulated: list[str] = []
        try:
            for chunk in stream_feedback_raw(
                graph,
                payload.review_context if payload else None,
            ):
                accumulated.append(chunk)
                yield _sse("delta", {"content": chunk})
        except RuntimeError as e:
            yield _sse("error", {"message": str(e)})
            return
        except Exception as e:
            yield _sse("error", {"message": f"LLM 호출 실패: {e}"})
            return

        raw = "".join(accumulated)
        try:
            response = parse_feedback(graph, raw)
        except Exception as e:
            yield _sse("error", {"message": f"파싱 실패: {e}"})
            return

        yield _sse(
            "complete",
            {
                "items": [item.model_dump() for item in response.items],
                "summary": response.summary,
                "canvas_hash": response.canvas_hash,
            },
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 가 앞단에 있을 경우 buffer 끄기
        },
    )
