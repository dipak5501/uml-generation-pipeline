from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.jobs.runner import enqueue_batch
from app.schemas import BatchGenerateRequest, GenerateRequest, JobResponse
from app.services.artifacts import artifact_detail
from app.services.orchestration import (
    create_job,
    get_or_create_default_project,
    run_single_generation,
    update_job,
)
from app.settings import get_settings

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate")
def generate(req: GenerateRequest, session: Session = Depends(get_session)):
    settings = get_settings()
    project = get_or_create_default_project(session)
    project_id = req.project_id or project.id
    job = create_job(session, mode="single", total=1, project_id=project_id)
    update_job(session, job, status="running")
    try:
        artifact = run_single_generation(
            session,
            requirement=req.requirement,
            diagram_type=req.diagram_type,
            project_id=project_id,
            job_id=job.id,
            settings=settings,
        )
        update_job(session, job, status="completed", completed=1)
        detail = artifact_detail(session, artifact.id)
        return {"job_id": job.id, "artifact": detail}
    except Exception as exc:
        update_job(session, job, status="failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate/batch", response_model=JobResponse)
def generate_batch(req: BatchGenerateRequest, session: Session = Depends(get_session)):
    project = get_or_create_default_project(session)
    project_id = req.project_id or project.id

    if req.requirements:
        requirements = req.requirements
    elif req.requirement:
        # Expand into n_samples variations for demo datasets
        base = req.requirement.strip()
        requirements = [f"{base} (variant {i+1})" for i in range(req.n_samples)]
    else:
        # Sample prompts for demo generation
        requirements = [
            "Build an online bookstore with inventory, carts, and order checkout.",
            "Create a hospital appointment system with patients, doctors, and schedules.",
            "Design a fleet logistics platform with vehicles, routes, and shipments.",
            "Implement a learning management system with courses, students, and quizzes.",
        ][: req.n_samples]
        while len(requirements) < req.n_samples:
            requirements.append(requirements[len(requirements) % 4] + f" extension {len(requirements)}")

    job_id = enqueue_batch(session, requirements, list(req.diagram_types), project_id)
    from app.models import GenerationJob

    job = session.get(GenerationJob, job_id)
    assert job is not None
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
