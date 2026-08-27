from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.models import GenerationJob, RepairAttempt, RenderAttempt, UMLArtifact
from app.schemas import ArtifactDetail, ArtifactLibrary, ArtifactSummary, JobResponse
from app.security import require_api_access, resolve_artifact_image, safe_internal_error
from app.services.artifacts import artifact_detail, artifact_summary
from app.services.orchestration import apply_verification, score_image
from app.services.repair import repair_plantuml
from app.services.scoring import verify_scores
from app.settings import get_settings
from uml_pipeline.render import render_plantuml

router = APIRouter(prefix="/api", tags=["artifacts"])


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobResponse(
        id=job.id,
        status=job.status,
        mode=job.mode,
        total=job.total,
        completed=job.completed,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/jobs/{job_id}/artifacts", response_model=List[ArtifactDetail])
def list_job_artifacts(job_id: int, session: Session = Depends(get_session)):
    job = session.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    arts = session.exec(
        select(UMLArtifact).where(UMLArtifact.job_id == job_id).order_by(UMLArtifact.id.asc())
    ).all()
    return [artifact_detail(session, a.id) for a in arts if a.id is not None]


def _filtered_artifacts(
    *,
    diagram_type: Optional[str] = None,
    min_score: Optional[float] = None,
    render_status: Optional[str] = None,
    dataset_accepted: Optional[bool] = None,
    job_id: Optional[int] = None,
    q: Optional[str] = None,
    majority_accepted: Optional[bool] = None,
):
    stmt = select(UMLArtifact)
    if diagram_type:
        stmt = stmt.where(UMLArtifact.diagram_type == diagram_type)
    if render_status:
        stmt = stmt.where(UMLArtifact.render_status == render_status)
    if dataset_accepted is not None:
        stmt = stmt.where(UMLArtifact.dataset_accepted == dataset_accepted)
    if majority_accepted is not None:
        stmt = stmt.where(UMLArtifact.majority_accepted == majority_accepted)
    if job_id is not None:
        stmt = stmt.where(UMLArtifact.job_id == job_id)
    if min_score is not None:
        stmt = stmt.where(UMLArtifact.composite_score >= min_score)
    needle = re.sub(r"[%_]", " ", (q or "")).strip()[:120]
    if needle:
        stmt = stmt.where(UMLArtifact.source_requirement.ilike(f"%{needle}%"))
    return stmt


@router.get("/artifacts/library", response_model=ArtifactLibrary)
def artifact_library(
    diagram_type: Optional[str] = None,
    min_score: Optional[float] = None,
    render_status: Optional[str] = None,
    dataset_accepted: Optional[bool] = None,
    job_id: Optional[int] = None,
    q: Optional[str] = None,
    majority_accepted: Optional[bool] = None,
    limit: int = 24,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    """Paginated history of every generated diagram (for the gallery UI)."""
    filtered = _filtered_artifacts(
        diagram_type=diagram_type,
        min_score=min_score,
        render_status=render_status,
        dataset_accepted=dataset_accepted,
        majority_accepted=majority_accepted,
        job_id=job_id,
        q=q,
    )
    total = session.exec(select(func.count()).select_from(filtered.subquery())).one()
    page = (
        filtered.order_by(UMLArtifact.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
    )
    arts = session.exec(page).all()
    return ArtifactLibrary(
        total=int(total or 0),
        offset=max(0, offset),
        limit=max(1, min(limit, 100)),
        items=[artifact_summary(a) for a in arts],
    )


@router.get("/artifacts", response_model=List[ArtifactSummary])
def list_artifacts(
    diagram_type: Optional[str] = None,
    min_score: Optional[float] = None,
    render_status: Optional[str] = None,
    dataset_accepted: Optional[bool] = None,
    job_id: Optional[int] = None,
    q: Optional[str] = None,
    majority_accepted: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    stmt = _filtered_artifacts(
        diagram_type=diagram_type,
        min_score=min_score,
        render_status=render_status,
        dataset_accepted=dataset_accepted,
        majority_accepted=majority_accepted,
        job_id=job_id,
        q=q,
    )
    stmt = stmt.order_by(UMLArtifact.id.desc()).offset(max(0, offset)).limit(max(1, min(limit, 1000)))
    arts = session.exec(stmt).all()
    return [artifact_summary(a) for a in arts]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetail)
def get_artifact(artifact_id: int, session: Session = Depends(get_session)):
    detail = artifact_detail(session, artifact_id)
    if not detail:
        raise HTTPException(404, "Artifact not found")
    return detail


@router.get("/artifacts/{artifact_id}/image")
def get_image(artifact_id: int, session: Session = Depends(get_session)):
    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    path = resolve_artifact_image(a.image_path, settings.artifact_dir)
    if path is None:
        raise HTTPException(404, "Image not available")
    media = "image/png" if a.image_format == "png" else "image/svg+xml"
    return FileResponse(path, media_type=media)


@router.get("/artifacts/{artifact_id}/adaptation")
def get_adaptation(artifact_id: int, session: Session = Depends(get_session)):
    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    path = settings.artifact_dir / str(a.id) / "adaptation.json"
    if not path.is_file():
        return {"artifact_id": artifact_id, "events": [], "generator": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"artifact_id": artifact_id, "events": [], "generator": None}


@router.get("/artifacts/{artifact_id}/plantuml")
def get_plantuml(artifact_id: int, session: Session = Depends(get_session)):
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    return PlainTextResponse(a.plantuml_code)


@router.post("/artifacts/{artifact_id}/rescore", response_model=ArtifactDetail)
def rescore(
    artifact_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    if a.render_status != "success" or not a.image_path:
        raise HTTPException(400, "Cannot rescore: render failed or image missing (score remains 0)")

    img = resolve_artifact_image(a.image_path, settings.artifact_dir)
    if img is None:
        raise HTTPException(400, "Cannot rescore: image path invalid")

    scores, meta, _ = score_image(img, a.technical_spec, settings)
    verification = verify_scores(
        scores,
        settings.vlm_weight_map,
        render_ok=True,
        tau=settings.acceptance_tau,
        min_composite=settings.min_composite_for_dataset,
    )
    apply_verification(a, scores, meta, verification, session, clear_existing=True)
    session.add(a)
    session.commit()
    detail = artifact_detail(session, artifact_id)
    assert detail
    return detail


@router.post("/artifacts/{artifact_id}/repair", response_model=ArtifactDetail)
def repair_artifact(
    artifact_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")

    try:
        errors = [a.validation_messages or "manual repair requested"]
        result = repair_plantuml(
            a.plantuml_code,
            a.technical_spec,
            a.diagram_type,
            errors,
            settings=settings,
        )
        session.add(
            RepairAttempt(
                artifact_id=a.id,
                attempt_number=1,
                before_code=a.plantuml_code,
                after_code=result.code,
                reason=result.reason,
                success=result.success_validation,
            )
        )
        a.plantuml_code = result.code
        out_dir = settings.artifact_dir / str(a.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        img, err = render_plantuml(
            a.plantuml_code, out_dir, settings.plantuml_jar, fmt=settings.image_format
        )
        session.add(
            RenderAttempt(
                artifact_id=a.id,
                attempt_number=1,
                success=img is not None,
                error_output=err,
                image_path=str(img) if img else None,
                fmt=settings.image_format,
            )
        )
        if img:
            stable = out_dir / f"diagram.{settings.image_format}"
            if Path(img) != stable:
                shutil.copy2(img, stable)
            a.image_path = str(stable)
            a.render_status = "success"
            scores, meta, _ = score_image(stable, a.technical_spec, settings)
            verification = verify_scores(
                scores,
                settings.vlm_weight_map,
                render_ok=True,
                tau=settings.acceptance_tau,
                min_composite=settings.min_composite_for_dataset,
            )
            apply_verification(a, scores, meta, verification, session, clear_existing=True)
        else:
            a.render_status = "failed"
            a.composite_score = 0.0
            a.majority_accepted = False
            a.affirmative_votes = 0
            a.dataset_accepted = False
            zero = {k: 0 for k in settings.vlm_weight_map}
            verification = verify_scores(
                zero,
                settings.vlm_weight_map,
                render_ok=False,
                tau=settings.acceptance_tau,
                min_composite=settings.min_composite_for_dataset,
            )
            meta = {
                k: {"model_name": k, "available": True, "explanation": err, "raw_output": None}
                for k in zero
            }
            apply_verification(a, zero, meta, verification, session, clear_existing=True)
        session.add(a)
        session.commit()
        detail = artifact_detail(session, artifact_id)
        assert detail
        return detail
    except HTTPException:
        raise
    except Exception as exc:
        raise safe_internal_error(exc, context="repair") from exc
