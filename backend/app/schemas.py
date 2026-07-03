from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    company_name: str = Field(min_length=2, max_length=160)
    industry: str = Field(min_length=2, max_length=100)
    region: str = ""
    target_market: str = ""
    goal: str = ""
    profile: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    profile: dict[str, Any]


class ProjectOut(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime


class DimensionResult(BaseModel):
    key: str
    name: str
    score: float
    max_score: float
    evidence: list[str]
    pending: list[str]


class RiskResult(BaseModel):
    title: str
    level: Literal["高", "中", "低"]
    basis: str
    recommendation: str
    requires_review: bool = False
    evidence_status: Literal["supported", "insufficient"] = "insufficient"
    citations: list[dict[str, Any]] = Field(default_factory=list)


class ActionItem(BaseModel):
    phase: str
    task: str
    owner: str
    deliverable: str
    priority: Literal["高", "中", "低"]


class AssessmentOut(BaseModel):
    total_score: float
    completeness: float
    dimensions: list[DimensionResult]
    risks: list[RiskResult]
    action_plan: list[ActionItem]
    missing_fields: list[str]
    rule_version: str


class ReviewCreate(BaseModel):
    decision: Literal["approved", "rejected", "needs_revision"]
    comment: str = ""
    reviewer: str = "演示顾问"


class ReviewOut(ReviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime


class ProjectDetail(ProjectOut):
    assessment: AssessmentOut | None = None
    reviews: list[ReviewOut] = Field(default_factory=list)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    content_type: str
    status: str
    extracted_text: str
    created_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str
    value: Any
    filename: str
    excerpt: str
    confidence: float
    method: str


class ExtractionOut(BaseModel):
    extracted_profile: dict[str, Any]
    merged_profile: dict[str, Any]
    evidence: list[EvidenceOut]
    document_count: int
    extraction_mode: str = "local"
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class DataConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    field: str
    values: list[Any]
    evidence: list[dict[str, Any]]
    status: str
    created_at: datetime


class ConflictResolve(BaseModel):
    selected_value: Any
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=500)


class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    authority: str = Field(min_length=2, max_length=160)
    topic: str = Field(min_length=2, max_length=100)
    region: str = "全球"
    source_url: str
    published_at: str = ""
    content: str = Field(min_length=20)


class KnowledgeOut(KnowledgeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    protected: bool = False
    created_at: datetime


class KnowledgeSearchResult(BaseModel):
    id: int
    title: str
    authority: str
    topic: str
    region: str
    source_url: str
    excerpt: str
    score: float


class WorkflowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    operation: str
    provider: str
    status: str
    latency_ms: int
    fallback_used: bool
    error: str
    details: dict[str, Any]
    created_at: datetime


class MetricsSummary(BaseModel):
    total_runs: int
    successful_runs: int
    degraded_runs: int
    failed_runs: int
    success_rate: float
    average_latency_ms: float
    current_mode: str
    dify_configured: bool
    redis_available: bool


class TaskStatusOut(BaseModel):
    project_id: int
    operation: str
    provider: str
    status: str
    latency_ms: int
    fallback_used: bool
    source: Literal["redis", "mysql"]
    created_at: str


class EvaluationSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    by_category: dict[str, dict[str, int | float]]
    failures: list[dict[str, Any]]
