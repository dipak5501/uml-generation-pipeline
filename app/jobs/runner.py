"""Background job helpers (in-process threads)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlmodel import Session

from app.db import get_engine
from app.models import GenerationJob
from app.services.orchestration import create_job, get_or_create_default_project, run_single_generation, update_job
from app.settings import get_settings

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


@dataclass(frozen=True)
class JobItem:
    requirement: str
    diagram_type: str
    input_mode: str
    skip_vlm: bool = False
    skip_repair: bool = False
    skip_majority: bool = False


def _batch_worker(job_id: int, items: list[JobItem], project_id: int) -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        job = session.get(GenerationJob, job_id)
        if job is None:
            return
        update_job(session, job, status="running")
        completed = 0
        try:
            for item in items:
                run_single_generation(
                    session,
                    requirement=item.requirement,
                    diagram_type=item.diagram_type,
                    project_id=project_id,
                    job_id=job_id,
                    settings=settings,
                    input_mode=item.input_mode,
                    skip_vlm=item.skip_vlm,
                    skip_repair=item.skip_repair,
                    skip_majority=item.skip_majority,
                )
                completed += 1
                job = session.get(GenerationJob, job_id)
                if job:
                    update_job(session, job, completed=completed)
            job = session.get(GenerationJob, job_id)
            if job:
                update_job(session, job, status="completed", completed=completed)
        except Exception as visc:
            logger.exception("Batch job %s failed", job_id)
            job = session.get(GenerationJob, job_id)
            if job:
                update_job(session, job, status="failed", error=str(visc), completed=completed)


def submit_batch(job_id: int, items: list[JobItem], project_id: int) -> None:
    _executor.submit(_batch_worker, job_id, items, project_id)


def enqueue_batch(
    session: Session,
    requirements: list[str],
    diagram_types: list[str],
    project_id: int | None = None,
    *,
    input_mode: str = "requirement",
    skip_vlm: bool = False,
    skip_repair: bool = False,
    skip_majority: bool = False,
) -> int:
    if project_id is None:
        project_id = get_or_create_default_project(session).id
    assert project_id is not None

    items: list[JobItem] = []
    for req in requirements:
        for dt in diagram_types:
            items.append(
                JobItem(
                    requirement=req,
                    diagram_type=dt,
                    input_mode=input_mode,
                    skip_vlm=skip_vlm,
                    skip_repair=skip_repair,
                    skip_majority=skip_majority,
                )
            )

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
    skip_vlm: bool = False,
    skip_repair: bool = False,
    skip_majority: bool = False,
) -> int:
    """Queue one requirement across one or more diagram types (runs in background)."""
    if project_id is None:
        project_id = get_or_create_default_project(session).id
    assert project_id is not None
    types = [dt for dt in diagram_types if dt]
    if not types:
        types = ["class"]
    items = [
        JobItem(
            requirement=requirement,
            diagram_type=dt,
            input_mode=input_mode,
            skip_vlm=skip_vlm,
            skip_repair=skip_repair,
            skip_majority=skip_majority,
        )
        for dt in types
    ]
    job = create_job(session, mode=mode, total=len(items), project_id=project_id)
    submit_batch(job.id, items, project_id)
    return job.id
