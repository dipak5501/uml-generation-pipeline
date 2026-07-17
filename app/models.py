"""SQLModel persistence entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class GenerationJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    mode: str = "single"  # single | batch
    status: str = "pending"  # pending|running|completed|failed
    total: int = 1
    completed: int = 0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RequirementInput(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="generationjob.id", index=True)
    raw_text: str
    diagram_type: str
    created_at: datetime = Field(default_factory=utcnow)


class TechnicalSpecification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: int = Field(foreign_key="requirementinput.id", index=True)
    raw_text: str
    structured_json: Optional[str] = None
    prompt_name: str = "requirement_to_tech_spec"
    prompt_version: str = "v1"
    model_name: str = ""
    provider: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class UMLArtifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="generationjob.id", index=True)
    requirement_id: Optional[int] = Field(default=None, foreign_key="requirementinput.id")
    specification_id: Optional[int] = Field(default=None, foreign_key="technicalspecification.id")
    project_id: int = Field(foreign_key="project.id", index=True)
    diagram_type: str = Field(index=True)
    source_requirement: str = ""
    technical_spec: str = ""
    plantuml_code: str = ""
    render_status: str = "pending"  # pending|success|failed
    image_path: Optional[str] = None
    image_format: str = "png"
    composite_score: float = 0.0
    majority_accepted: bool = False
    affirmative_votes: int = 0
    dataset_accepted: bool = False
    acceptance_tau: float = 4.0
    used_cot: bool = False
    prompt_name: str = ""
    prompt_version: str = "v1"
    code_model: str = ""
    provider: str = ""
    validation_messages: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RenderAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="umlartifact.id", index=True)
    attempt_number: int = 1
    success: bool = False
    error_output: Optional[str] = None
    image_path: Optional[str] = None
    fmt: str = "png"
    created_at: datetime = Field(default_factory=utcnow)


class RepairAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="umlartifact.id", index=True)
    attempt_number: int = 1
    before_code: str = ""
    after_code: str = ""
    reason: str = ""
    success: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class ModelScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="umlartifact.id", index=True)
    model_key: str
    model_name: str = ""
    score: int = 0
    weight: float = 0.0
    explanation: Optional[str] = None
    available: bool = True
    raw_output: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class CompositeScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="umlartifact.id", index=True)
    final_score: float = 0.0
    majority_accepted: bool = False
    affirmative_votes: int = 0
    dataset_accepted: bool = False
    tau: float = 4.0
    formula_snapshot: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Reviewer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: str = "expert"
    created_at: datetime = Field(default_factory=utcnow)


class HumanReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="umlartifact.id", index=True)
    reviewer_id: int = Field(foreign_key="reviewer.id")
    semantic_correctness: int = Field(ge=1, le=5)
    structural_completeness: int = Field(ge=1, le=5)
    syntactic_accuracy: int = Field(ge=1, le=5)
    overall_coherence: int = Field(ge=1, le=5)
    comments: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def mean_score(self) -> float:
        return (
            self.semantic_correctness
            + self.structural_completeness
            + self.syntactic_accuracy
            + self.overall_coherence
        ) / 4.0


class PromptTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    version: str = "v1"
    body: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class SystemConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    value: str = ""
    updated_at: datetime = Field(default_factory=utcnow)
