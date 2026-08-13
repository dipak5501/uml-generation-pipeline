from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db import get_session
from app.jobs.runner import enqueue_batch, enqueue_generation
from app.schemas import BatchGenerateRequest, GenerateRequest, JobResponse
from app.security import MAX_SAMPLES_LIMIT, require_api_access, safe_internal_error
from app.services.artifacts import artifact_detail
from app.services.orchestration import (
    create_job,
    get_or_create_default_project,
    run_single_generation,
    update_job,
)
from app.settings import ROOT, get_settings

router = APIRouter(prefix="/api", tags=["generate"])


def _job_response(job) -> JobResponse:
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

SAMPLE_FILE = ROOT / "sample_data" / "requirements.txt"


def _load_sample_requirements(limit: int) -> list[str]:
    if SAMPLE_FILE.is_file():
        lines = [ln.strip() for ln in SAMPLE_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            out: list[str] = []
            i = 0
            while len(out) < limit:
                if i < len(lines):
                    out.append(lines[i])
                else:
                    out.append(f"{lines[i % len(lines)]} (variant {i + 1})")
                i += 1
            return out
    fallback = [
        "Build an online bookstore with inventory, carts, and order checkout.",
        "Create a hospital appointment system with patients, doctors, and schedules.",
        "Design a fleet logistics platform with vehicles, routes, and shipments.",
        "Implement a learning management system with courses, students, and quizzes.",
    ]
    out = []
    i = 0
    while len(out) < limit:
        base = fallback[i % len(fallback)]
        out.append(base if i < len(fallback) else f"{base} (variant {i + 1})")
        i += 1
    return out


@router.post("/generate")
def generate(
    req: GenerateRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    """Turn requirements or source code into PlantUML + paper-style multimodal validation.

    Default ``async_mode=true`` queues a background job and returns immediately so the
    Streamlit UI can change pages without cancelling generation.
    """
    settings = get_settings()
    project = get_or_create_default_project(session)
    project_id = req.project_id or project.id
    types = list(req.diagram_types) if req.diagram_types else [req.diagram_type]

    if req.async_mode:
        job_id = enqueue_generation(
            session,
            req.requirement,
            types,
            input_mode=req.input_mode,
            project_id=project_id,
            mode="single" if len(types) == 1 else "multi",
        )
        from app.models import GenerationJob

        job = session.get(GenerationJob, job_id)
        assert job is not None
        return {"job_id": job.id, "job": _job_response(job), "async": True, "artifact": None}

    # Synchronous path (tests / scripts)
    if len(types) != 1:
        raise HTTPException(400, "Sync generate supports one diagram_type; use async_mode for multiple")
    job = create_job(session, mode="single", total=1, project_id=project_id)
    update_job(session, job, status="running")
    try:
        artifact = run_single_generation(
            session,
            requirement=req.requirement,
            diagram_type=types[0],
            project_id=project_id,
            job_id=job.id,
            settings=settings,
            input_mode=req.input_mode,
        )
        update_job(session, job, status="completed", completed=1)
        detail = artifact_detail(session, artifact.id)
        return {"job_id": job.id, "job": _job_response(job), "async": False, "artifact": detail}
    except Exception as exc:
        update_job(session, job, status="failed", error=str(exc)[:500])
        raise safe_internal_error(exc, context="generate") from exc


@router.post("/generate/batch", response_model=JobResponse)
def generate_batch(
    req: BatchGenerateRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    project = get_or_create_default_project(session)
    project_id = req.project_id or project.id

    if req.requirements:
        requirements = [r.strip() for r in req.requirements if r and r.strip()]
    elif req.requirement:
        base = req.requirement.strip()
        requirements = [f"{base} (variant {i+1})" for i in range(req.n_samples)]
    elif req.use_sample_file:
        requirements = _load_sample_requirements(req.n_samples)
    else:
        requirements = _load_sample_requirements(req.n_samples)

    if not requirements:
        raise HTTPException(400, "No requirements provided")

    job_id = enqueue_batch(session, requirements, list(req.diagram_types), project_id)
    from app.models import GenerationJob

    job = session.get(GenerationJob, job_id)
    assert job is not None
    return _job_response(job)


@router.get("/samples")
def list_samples(limit: int = Query(default=50, ge=1, le=MAX_SAMPLES_LIMIT)):
    """Preview built-in sample requirement sentences."""
    return {"count": limit, "requirements": _load_sample_requirements(limit)}
