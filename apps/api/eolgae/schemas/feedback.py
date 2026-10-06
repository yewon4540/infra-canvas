"""AI 피드백 응답 스키마.

[Final Goal #3 AI 기반 보안/비용/HA/운영 평가] 의 1차 MVP 구현.
Well-Architected 5 pillars 중 4개 (Sustainability 제외) 차원에서 피드백.
"""
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
Category = Literal["security", "cost", "ha", "operations"]
Environment = Literal["unknown", "dev", "staging", "production"]
AvailabilityTarget = Literal["unknown", "best_effort", "business_hours", "high_availability"]
DataSensitivity = Literal["unknown", "public", "internal", "personal_data", "payment"]
CostPosture = Literal["unknown", "cheapest", "balanced", "production_safe"]
TrafficExpectation = Literal["unknown", "small", "medium", "high"]


class ReviewContext(BaseModel):
    """사용자가 AI 피드백에 제공하는 설계 의도/검토 기준."""

    purpose: str = Field(default="", description="무엇을 만들려는지")
    environment: Environment = "unknown"
    availability_target: AvailabilityTarget = "unknown"
    cost_posture: CostPosture = "unknown"
    traffic_expectation: TrafficExpectation = "unknown"
    notes: str = Field(default="", description="추가 설계 메모")


class FeedbackRequest(BaseModel):
    """AI 피드백 요청 body."""

    review_context: ReviewContext | None = None


class FeedbackItem(BaseModel):
    """단일 피드백 항목."""

    category: Category
    severity: Severity
    title: str = Field(description="짧은 제목 (한국어, 60자 이내)")
    description: str = Field(description="상세 설명 (한국어)")
    target_node_id: str | None = Field(
        default=None,
        description="영향받는 노드 ID (특정 노드 무관하면 null)",
    )
    target_edge_id: str | None = Field(default=None)
    recommendation: str | None = Field(
        default=None,
        description="권장 조치 (한국어)",
    )


class FeedbackResponse(BaseModel):
    """피드백 엔진 응답."""

    items: list[FeedbackItem]
    summary: str = Field(description="전체 요약 (한국어)")
    canvas_hash: str = Field(description="캐싱용 해시")
