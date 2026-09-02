from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models import HumanReview, UMLArtifact
from app.schemas import HumanReviewCreate, HumanReviewOut
from app.security import require_api_access
from app.services.analytics import get_or_create_reviewer

router = APIRouter(prefix="/api", tags=["human-review"])


@router.post("/human-review", response_model=HumanReviewOut)
def create_human_review(
    payload: HumanReviewCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    artifact = session.get(UMLArtifact, payload.artifact_id)
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    reviewer = get_or_create_reviewer(session, payload.reviewer_name, payload.reviewer_role)
    review = HumanReview(
        artifact_id=payload.artifact_id,
        reviewer_id=reviewer.id,
        semantic_correctness=payload.semantic_correctness,
        structural_completeness=payload.structural_completeness,
        syntactic_accuracy=payload.syntactic_accuracy,
        overall_coherence=payload.overall_coherence,
        score_scale=payload.score_scale,
        comments=payload.comments,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return HumanReviewOut(
        id=review.id,
        artifact_id=review.artifact_id,
        reviewer_name=reviewer.name,
        reviewer_role=reviewer.role,
        semantic_correctness=review.semantic_correctness,
        structural_completeness=review.structural_completeness,
        syntactic_accuracy=review.syntactic_accuracy,
        overall_coherence=review.overall_coherence,
        score_scale=getattr(review, "score_scale", 6) or 6,
        mean_score=review.mean_score,
        comments=review.comments,
        created_at=review.created_at,
    )
