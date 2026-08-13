"""Background job helpers (in-process threads)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session

from app.db import get_engine
from app.models import GenerationJob
from app.services.orchestration import create_job, get_or_create_default_project, run_single_generation, update_job
from app.settings import get_settings

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)

# (requirement, diagram_type, input_mode)
JobItem = tuple[str, str, str]


def _batch_worker(job_id: int, items: list[JobItem], project_id: int) -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        job = session.get(GenerationJob, job_id)
        if job is None:
            return
        update_job(session, job, status="running")
        completed = 0
        try:
            for requirement, diagram_type, input_mode in items:
                run_single_generation(
                    session,
                    requirement=requirement,
                    diagram_type=diagram_type,
                    project_id=project_id,
                    job_id=job_id,
                    settings=settings,
                    input_mode=input_mode,
                )
                completed += 1
                job = session.get(GenerationJob, job_id)
                if job:
                    update_job(session, job, completed=completed)
            job = session.get(GenerationJob, job_id)
            if job:
                update_job(session, job, status="completed", completed=completed)
        except Exception as exc:
            logger.exception("Batch job %s failed", job_id)
            job = session.get(GenerationJob, job_id)
            if job:
                update_job(session, job, status="failed", error=str(exc), completed=completed)


def submit_batch(job_id: int, items: list[JobItem], project_id: int) -> None:
    _executor.submit(_batch_worker, job_id, items, project_id)


def enqueue_batch(
    session: Session,
    requirements: list[str],
    diagram_types: list[str],
    project_id: int | None = None,
    *,
    input_mode: str = "requirement",
) -> int:
    if project_id is None:
        project_id = get_or_create_default_project(session).id
    assert project_id is not None

    items: list[JobItem] = []
    for req in requirements:
        for dt in diagram_types:
            items.append((req, dt, input_mode))

    job = create_job(session, mode="batch", total=len(items), project_id=project_id)
    submit_batch(job.id, items, project_id)
    return job.id


def enqueue_generation(
    session: Session,
    requirement: str,
    diagram_types: list[str],
    *,
    input_mode: str = "requirement",
    project_id: int | None = None,
    mode: str = "single",
) -> int:
    """Queue one requirement across one or more diagram types (runs in background)."""
    if project_id is None:
        project_id = get_or_create_default_project(session).id
    assert project_id is not None
    types = [dt for dt in diagram_types if dt]
    if not types:
        types = ["class"]
    items: list[JobItem] = [(requirement, dt, input_mode) for dt in types]
    job = create_job(session, mode=mode, total=len(items), project_id=project_id)
    submit_batch(job.id, items, project_id)
    return job.id
