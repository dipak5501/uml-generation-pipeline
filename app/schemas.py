"""Pydantic API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

InputMode = Literal["requirement", "source_code"]

DiagramType = Literal["class", "object", "component", "package", "flowchart"]

ALL_DIAGRAM_TYPES: list[DiagramType] = [
    "class",
    "object",
    "component",
    "package",
    "flowchart",
]


class GenerateRequest(BaseModel):
    """Generate UML from natural-language requirements or source code."""

    requirement: str = Field(
        min_length=3,
        description="Plain-English requirement OR source code (depending on input_mode)",
    )
    diagram_type: DiagramType = "class"
    input_mode: InputMode = "requirement"
    project_id: Optional[int] = None
    async_mode: bool = False


class BatchGenerateRequest(BaseModel):
    requirement: Optional[str] = None
    requirements: Optional[list[str]] = None
    diagram_types: list[DiagramType] = Field(
        default_factory=lambda: list(ALL_DIAGRAM_TYPES)
    )
    n_samples: int = Field(default=50, ge=1, le=500)
    use_sample_file: bool = True
    project_id: Optional[int] = None


class JobResponse(BaseModel):
    id: int
    status: str
    mode: str
    total: int
    completed: int
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ModelScoreOut(BaseModel):
    model_key: str
    model_name: str
    score: int
    weight: float
    available: bool
    explanation: Optional[str] = None


class RepairAttemptOut(BaseModel):
    attempt_number: int
    reason: str
    success: bool
    before_code: str
    after_code: str


class RenderAttemptOut(BaseModel):
    attempt_number: int
    success: bool
    error_output: Optional[str] = None
    image_path: Optional[str] = None


class HumanReviewCreate(BaseModel):
    artifact_id: int
    reviewer_name: str
    reviewer_role: str = "expert"
    semantic_correctness: int = Field(ge=1, le=5)
    structural_completeness: int = Field(ge=1, le=5)
    syntactic_accuracy: int = Field(ge=1, le=5)
    overall_coherence: int = Field(ge=1, le=5)
    comments: str = ""


class HumanReviewOut(BaseModel):
    id: int
    artifact_id: int
    reviewer_name: str
    reviewer_role: str
    semantic_correctness: int
    structural_completeness: int
    syntactic_accuracy: int
    overall_coherence: int
    mean_score: float
    comments: str
    created_at: datetime


class ArtifactSummary(BaseModel):
    id: int
    diagram_type: str
    render_status: str
    composite_score: float
    majority_accepted: bool = False
    dataset_accepted: bool = False
    source_requirement: str
    created_at: datetime


class ArtifactDetail(BaseModel):
    id: int
    diagram_type: str
    source_requirement: str
    technical_spec: str
    plantuml_code: str
    render_status: str
    image_path: Optional[str]
    image_format: str
    composite_score: float
    majority_accepted: bool = False
    affirmative_votes: int = 0
    dataset_accepted: bool = False
    acceptance_tau: float = 4.0
    used_cot: bool = False
    validation_messages: Optional[str]
    model_scores: list[ModelScoreOut]
    render_attempts: list[RenderAttemptOut]
    repair_attempts: list[RepairAttemptOut]
    human_reviews: list[HumanReviewOut]
    created_at: datetime
    updated_at: datetime


class AnalyticsSummary(BaseModel):
    total_artifacts: int
    by_diagram_type: dict
    mean_composite: Optional[float]
    render_failures: int
    repair_attempts: int
    repair_successes: int
    package_failure_count: int
    human_review_count: int
    human_vs_ai_correlation: Optional[float] = None
    majority_accepted_count: int = 0
    dataset_accepted_count: int = 0
    majority_acceptance_rate: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    provider: str
    mock_providers: bool
    database_ok: bool
    plantuml_jar_present: bool
    java_available: bool
    messages: list[str]
