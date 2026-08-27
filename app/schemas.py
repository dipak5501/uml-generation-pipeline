"""Pydantic API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.security import MAX_BATCH_ITEMS, MAX_REQUIREMENT_CHARS

InputMode = Literal["requirement", "source_code"]

DiagramType = Literal["class", "object", "component", "package"]

ALL_DIAGRAM_TYPES: list[DiagramType] = [
    "class",
    "object",
    "component",
    "package",
]


class GenerateRequest(BaseModel):
    """Generate UML from natural-language requirements or source code."""

    requirement: str = Field(
        min_length=3,
        max_length=MAX_REQUIREMENT_CHARS,
        description="Plain-English requirement OR source code (depending on input_mode)",
    )
    diagram_type: DiagramType = "class"
    diagram_types: Optional[list[DiagramType]] = Field(
        default=None,
        description="When set (async), generate all listed types in one background job",
    )
    input_mode: InputMode = "requirement"
    project_id: Optional[int] = None
    # Default true so UI navigation does not cancel in-flight HTTP generate calls.
    async_mode: bool = True
    # Skip the 3-VLM ensemble (Qwen/LLaMA/Aya). Diagram + acceptance still run.
    skip_vlm: bool = False

    @field_validator("requirement", mode="before")
    @classmethod
    def _strip_requirement(cls, value: object) -> object:
        # Reject whitespace-only bodies that would otherwise pass min_length=3.
        if isinstance(value, str):
            return value.strip()
        return value


class BatchGenerateRequest(BaseModel):
    requirement: Optional[str] = Field(default=None, max_length=MAX_REQUIREMENT_CHARS)
    requirements: Optional[list[str]] = None
    diagram_types: list[DiagramType] = Field(
        default_factory=lambda: list(ALL_DIAGRAM_TYPES)
    )
    n_samples: int = Field(default=50, ge=1, le=200)
    use_sample_file: bool = True
    project_id: Optional[int] = None

    @field_validator("requirements")
    @classmethod
    def _cap_requirement_strings(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        if len(value) > MAX_BATCH_ITEMS:
            raise ValueError(f"At most {MAX_BATCH_ITEMS} requirements allowed")
        cleaned: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item)
            if len(text) > MAX_REQUIREMENT_CHARS:
                raise ValueError(
                    f"Each requirement must be ≤ {MAX_REQUIREMENT_CHARS} characters"
                )
            cleaned.append(text)
        return cleaned

    @model_validator(mode="after")
    def _cap_cartesian_product(self) -> "BatchGenerateRequest":
        n_req = (
            len(self.requirements)
            if self.requirements
            else (self.n_samples if self.requirement or self.use_sample_file else 0)
        )
        n_types = max(len(self.diagram_types), 1)
        if n_req * n_types > MAX_BATCH_ITEMS:
            raise ValueError(
                f"Batch would create {n_req * n_types} artifacts; "
                f"limit is {MAX_BATCH_ITEMS} (reduce n_samples or diagram_types)"
            )
        return self


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
    raw_output: Optional[str] = None


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
    comments: str = Field(default="", max_length=4000)


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
    input_mode: str = "requirement"
    source_language: Optional[str] = None
    source_requirement: str
    created_at: datetime
    has_image: bool = False
    job_id: Optional[int] = None


class ArtifactLibrary(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ArtifactSummary]


class ArtifactDetail(BaseModel):
    id: int
    diagram_type: str
    input_mode: str = "requirement"
    source_language: Optional[str] = None
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
    package_failure_taxonomy: dict[str, int] = Field(default_factory=dict)
    human_review_count: int
    human_vs_ai_correlation: Optional[float] = None
    majority_accepted_count: int = 0
    dataset_accepted_count: int = 0
    majority_acceptance_rate: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    provider: str
    provider_summary: str = ""
    mock_providers: bool
    use_finetuned_code: bool = False
    finetuned_adapter_path: Optional[str] = None
    finetuned_adapter_present: bool = False
    database_ok: bool
    plantuml_jar_present: bool
    java_available: bool
    auth_required: bool = False
    remote_agent_available: bool = True
    messages: list[str]


class AgentCommandRequest(BaseModel):
    command: str = Field(
        description="Allowlisted command: health, restart-api, restart-ui, smoke-test, "
        "generate, training-status, server-status, agent-prompt"
    )
    args: dict = Field(default_factory=dict, description="Command-specific arguments")


class AgentCommandResponse(BaseModel):
    task_id: str
    command: str
    status: str


class AgentTaskResponse(BaseModel):
    task_id: str
    command: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[dict] = None
    output: str = ""
    error: Optional[str] = None


class AgentHealthResponse(BaseModel):
    status: str
    agent: str
    version: str
    auth_required: bool
    cursor_sdk_available: bool
    cursor_agent_enabled: bool
    allowed_commands: list[str]
    active_tasks: int
    rate_limit_per_minute: int
