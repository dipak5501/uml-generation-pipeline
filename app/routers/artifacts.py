from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import CompositeScore, GenerationJob, ModelScore, RepairAttempt, RenderAttempt, UMLArtifact
from app.schemas import ArtifactDetail, ArtifactSummary, JobResponse
from app.services.artifacts import artifact_detail, artifact_summary
from app.services.repair import repair_plantuml
from app.services.scoring import formula_snapshot
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


@router.get("/artifacts", response_model=List[ArtifactSummary])
def list_artifacts(
    diagram_type: Optional[str] = None,
    min_score: Optional[float] = None,
    render_status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    q = select(UMLArtifact)
    arts = session.exec(q).all()
    out = []
    for a in arts:
        if diagram_type and a.diagram_type != diagram_type:
            continue
        if min_score is not None and a.composite_score < min_score:
            continue
        if render_status and a.render_status != render_status:
            continue
        out.append(artifact_summary(a))
    out.sort(key=lambda x: x.id, reverse=True)
    return out


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetail)
def get_artifact(artifact_id: int, session: Session = Depends(get_session)):
    detail = artifact_detail(session, artifact_id)
    if not detail:
        raise HTTPException(404, "Artifact not found")
    return detail


@router.get("/artifacts/{artifact_id}/image")
def get_image(artifact_id: int, session: Session = Depends(get_session)):
    a = session.get(UMLArtifact, artifact_id)
    if not a or not a.image_path or not Path(a.image_path).is_file():
        raise HTTPException(404, "Image not available")
    media = "image/png" if a.image_format == "png" else "image/svg+xml"
    return FileResponse(a.image_path, media_type=media)


@router.get("/artifacts/{artifact_id}/plantuml")
def get_plantuml(artifact_id: int, session: Session = Depends(get_session)):
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    return PlainTextResponse(a.plantuml_code)


@router.post("/artifacts/{artifact_id}/rescore", response_model=ArtifactDetail)
def rescore(artifact_id: int, session: Session = Depends(get_session)):
    from app.services.orchestration import score_image

    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    if a.render_status != "success" or not a.image_path:
        raise HTTPException(400, "Cannot rescore: render failed or image missing (score remains 0)")

    # clear old scores
    old = session.exec(select(ModelScore).where(ModelScore.artifact_id == artifact_id)).all()
    for o in old:
        session.delete(o)
    oldc = session.exec(select(CompositeScore).where(CompositeScore.artifact_id == artifact_id)).all()
    for o in oldc:
        session.delete(o)
    session.commit()

    scores, meta, composite = score_image(Path(a.image_path), a.technical_spec, settings)
    a.composite_score = composite
    session.add(a)
    for key, weight in settings.vlm_weight_map.items():
        m = meta.get(key, {})
        session.add(
            ModelScore(
                artifact_id=a.id,
                model_key=key,
                model_name=str(m.get("model_name", key)),
                score=int(scores.get(key, 0)),
                weight=weight,
                available=bool(m.get("available", True)),
                explanation=m.get("explanation"),
                raw_output=m.get("raw_output"),
            )
        )
    session.add(
        CompositeScore(
            artifact_id=a.id,
            final_score=composite,
            formula_snapshot=formula_snapshot(scores, settings.vlm_weight_map, composite),
        )
    )
    session.commit()
    detail = artifact_detail(session, artifact_id)
    assert detail
    return detail


@router.post("/artifacts/{artifact_id}/repair", response_model=ArtifactDetail)
def repair_artifact(artifact_id: int, session: Session = Depends(get_session)):
    settings = get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")

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
    img, err = render_plantuml(a.plantuml_code, out_dir, settings.plantuml_jar, fmt=settings.image_format)
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
        from app.services.orchestration import score_image

        scores, meta, composite = score_image(stable, a.technical_spec, settings)
        a.composite_score = composite
        for key, weight in settings.vlm_weight_map.items():
            m = meta.get(key, {})
            session.add(
                ModelScore(
                    artifact_id=a.id,
                    model_key=key,
                    model_name=str(m.get("model_name", key)),
                    score=int(scores.get(key, 0)),
                    weight=weight,
                    available=bool(m.get("available", True)),
                    explanation=m.get("explanation"),
                    raw_output=m.get("raw_output"),
                )
            )
        session.add(
            CompositeScore(
                artifact_id=a.id,
                final_score=composite,
                formula_snapshot=formula_snapshot(scores, settings.vlm_weight_map, composite),
            )
        )
    else:
        a.render_status = "failed"
        a.composite_score = 0.0
    session.add(a)
    session.commit()
    detail = artifact_detail(session, artifact_id)
    assert detail
    return detail
