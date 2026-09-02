"""Artifact serialization helpers."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    HumanReview,
    ModelScore,
    RepairAttempt,
    RenderAttempt,
    Reviewer,
    UMLArtifact,
)
from app.schemas import (
    ArtifactDetail,
    ArtifactSummary,
    HumanReviewOut,
    ModelScoreOut,
    RepairAttemptOut,
    RenderAttemptOut,
)


def artifact_summary(a: UMLArtifact) -> ArtifactSummary:
    return ArtifactSummary(
        id=a.id,
        diagram_type=a.diagram_type,
        render_status=a.render_status,
        composite_score=a.composite_score,
        majority_accepted=a.majority_accepted,
        dataset_accepted=a.dataset_accepted,
        input_mode=a.input_mode,
        source_language=a.source_language,
        source_requirement=a.source_requirement,
        created_at=a.created_at,
        has_image=bool(a.image_path) and a.render_status == "success",
        job_id=a.job_id,
    )


def artifact_detail(session: Session, artifact_id: int) -> ArtifactDetail | None:
    a = session.get(UMLArtifact, artifact_id)
    if a is None:
        return None

    scores = session.exec(select(ModelScore).where(ModelScore.artifact_id == artifact_id)).all()
    # Hydrate raw_output via SQL in case the running process's ORM mapper was
    # created before the column existed (stale LaunchAgent without restart).
    raw_by_key: dict[str, str | None] = {}
    try:
        from sqlalchemy import text

        rows = session.connection().execute(
            text("SELECT model_key, raw_output FROM modelscore WHERE artifact_id = :aid"),
            {"aid": artifact_id},
        )
        for model_key, raw in rows:
            raw_by_key[str(model_key)] = raw
    except Exception:
        pass

    renders = session.exec(select(RenderAttempt).where(RenderAttempt.artifact_id == artifact_id)).all()
    repairs = session.exec(select(RepairAttempt).where(RepairAttempt.artifact_id == artifact_id)).all()
    reviews = session.exec(select(HumanReview).where(HumanReview.artifact_id == artifact_id)).all()

    human_outs: list[HumanReviewOut] = []
    for r in reviews:
        reviewer = session.get(Reviewer, r.reviewer_id)
        human_outs.append(
            HumanReviewOut(
                id=r.id,
                artifact_id=r.artifact_id,
                reviewer_name=reviewer.name if reviewer else "unknown",
                reviewer_role=reviewer.role if reviewer else "",
                semantic_correctness=r.semantic_correctness,
                structural_completeness=r.structural_completeness,
                syntactic_accuracy=r.syntactic_accuracy,
                overall_coherence=r.overall_coherence,
                score_scale=getattr(r, "score_scale", 6) or 6,
                mean_score=r.mean_score,
                comments=r.comments,
                created_at=r.created_at,
            )
        )

    return ArtifactDetail(
        id=a.id,
        diagram_type=a.diagram_type,
        input_mode=a.input_mode,
        source_language=a.source_language,
        source_requirement=a.source_requirement,
        technical_spec=a.technical_spec,
        plantuml_code=a.plantuml_code,
        render_status=a.render_status,
        image_path=a.image_path,
        image_format=a.image_format,
        composite_score=a.composite_score,
        majority_accepted=a.majority_accepted,
        affirmative_votes=a.affirmative_votes,
        dataset_accepted=a.dataset_accepted,
        acceptance_tau=a.acceptance_tau,
        used_cot=a.used_cot,
        validation_messages=a.validation_messages,
        model_scores=[
            ModelScoreOut(
                model_key=s.model_key,
                model_name=s.model_name,
                score=s.score,
                weight=s.weight,
                available=s.available,
                explanation=s.explanation,
                raw_output=s.raw_output if s.raw_output is not None else raw_by_key.get(s.model_key),
            )
            for s in scores
        ],
        render_attempts=[
            RenderAttemptOut(
                attempt_number=r.attempt_number,
                success=r.success,
                error_output=r.error_output,
                image_path=r.image_path,
            )
            for r in renders
        ],
        repair_attempts=[
            RepairAttemptOut(
                attempt_number=r.attempt_number,
                reason=r.reason,
                success=r.success,
                before_code=r.before_code,
                after_code=r.after_code,
            )
            for r in repairs
        ],
        human_reviews=human_outs,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
