"""Pydantic schemas for Canvas API.

CANVAS-SCHEMA.md 정의 따름. snake_case 사용.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CanvasState = Literal["design", "deploy", "running", "applied", "destroyed"]
CanvasKind = Literal["aws", "kubernetes", "multi_architecture"]


class Position(BaseModel):
    x: float
    y: float


class Size(BaseModel):
    width: float
    height: float


class Node(BaseModel):
    id: str
    type: str
    display_name: str = ""
    position: Position
    size: Size | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_group_id: str | None = None
    aws_binding: dict[str, Any] | None = None


class Edge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "network"
    properties: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Group(BaseModel):
    id: str
    type: str
    display_name: str = ""
    position: Position
    size: Size | None = None
    contained_node_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_group_id: str | None = None


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)


class AwsAccount(BaseModel):
    aws_connection_id: str | None = None
    account_id: str | None = None
    default_region: str = "ap-northeast-2"
    default_tags: dict[str, str] = Field(default_factory=dict)
    external_id: str | None = None
    role_arn: str | None = None
    binding_status: str | None = None
    last_verified_at: str | None = None
    assumed_arn: str | None = None


class CanvasBase(BaseModel):
    name: str = "Untitled"
    description: str | None = None
    schema_version: str = "0.1.0"
    state: CanvasState = "design"
    canvas_kind: CanvasKind = "aws"
    graph: Graph = Field(default_factory=Graph)
    aws_connection_id: UUID | None = None
    aws_account: AwsAccount | None = None
    group_id: UUID | None = None
    environment_id: UUID | None = None
    target_id: UUID | None = None


class CanvasCreate(CanvasBase):
    pass


class CanvasDuplicateRequest(BaseModel):
    name: str | None = None


class CanvasTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    node_count: int
    edge_count: int


class CanvasFragmentResponse(BaseModel):
    id: str
    name: str
    description: str
    node_count: int
    edge_count: int


class CanvasFromTemplateRequest(BaseModel):
    template_id: str
    name: str | None = None
    aws_connection_id: UUID | None = None
    group_id: UUID | None = None
    environment_id: UUID | None = None


class CanvasInsertFragmentRequest(BaseModel):
    fragment_id: str
    x: float = 80
    y: float = 80


class CanvasUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    state: CanvasState | None = None
    graph: Graph | None = None
    aws_connection_id: UUID | None = None
    aws_account: AwsAccount | None = None
    group_id: UUID | None = None
    environment_id: UUID | None = None
    target_id: UUID | None = None


class CanvasResponse(CanvasBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
