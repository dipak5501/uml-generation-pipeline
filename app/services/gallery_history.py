"""Import previously captured live diagrams into the Generated Diagrams gallery."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.models import (
    CompositeScore,
    GenerationJob,
    ModelScore,
    RenderAttempt,
    UMLArtifact,
)
from app.services.orchestration import get_or_create_default_project
from app.settings import ROOT

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_DIR = ROOT / "sample_data" / "gallery_history"


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def catalog_dir() -> Path:
    return DEFAULT_CATALOG_DIR


def should_auto_import() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if os.environ.get("UML_SKIP_GALLERY_HISTORY", "").strip() in {"1", "true", "yes"}:
        return False
    return (DEFAULT_CATALOG_DIR / "catalog.json").is_file()


def import_gallery_history(
    session: Session,
    *,
    catalog_path: Path | None = None,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Insert missing catalog artifacts. Existing IDs are left unchanged (Mac-safe)."""
    path = catalog_path or (DEFAULT_CATALOG_DIR / "catalog.json")
    if not path.is_file():
        return {"inserted": [], "skipped": [], "jobs_inserted": []}

    catalog = json.loads(path.read_text(encoding="utf-8"))
    png_root = path.parent / "pngs"
    project = get_or_create_default_project(session)
    assert project.id is not None

    jobs_inserted: list[int] = []
    for job in catalog.get("jobs") or []:
        job_id = int(job["id"])
        if session.get(GenerationJob, job_id) is not None:
            continue
        session.add(
            GenerationJob(
                id=job_id,
                project_id=project.id,
                mode=str(job.get("mode") or "single"),
                status=str(job.get("status") or "completed"),
                total=int(job.get("total") or 1),
                completed=int(job.get("completed") or 0),
                created_at=_parse_dt(job.get("created_at")),
                updated_at=_parse_dt(job.get("updated_at") or job.get("created_at")),
            )
        )
        jobs_inserted.append(job_id)
    if jobs_inserted:
        session.flush()

    inserted: list[int] = []
    skipped: list[int] = []
    for row in catalog.get("artifacts") or []:
        art_id = int(row["id"])
        if session.get(UMLArtifact, art_id) is not None:
            skipped.append(art_id)
            continue
        png_name = str(row.get("png") or f"{art_id}.png")
        src = png_root / png_name
        if not src.is_file():
            logger.warning("gallery history missing PNG for #%s (%s)", art_id, src)
            skipped.append(art_id)
            continue
        dest_dir = artifact_dir / str(art_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "diagram.png"
        shutil.copy2(src, dest)

        created = _parse_dt(row.get("created_at"))
        job_id = int(row["job_id"]) if row.get("job_id") is not None else None
        artifact = UMLArtifact(
            id=art_id,
            job_id=job_id,
            project_id=project.id,
            diagram_type=str(row.get("diagram_type") or "class"),
            input_mode=str(row.get("input_mode") or "requirement"),
            source_language=row.get("source_language"),
            source_requirement=str(row.get("source_requirement") or ""),
            technical_spec=str(row.get("technical_spec") or ""),
            plantuml_code=str(row.get("plantuml_code") or ""),
            render_status=str(row.get("render_status") or "success"),
            image_path=str(dest),
            image_format=str(row.get("image_format") or "png"),
            composite_score=float(row.get("composite_score") or 0.0),
            majority_accepted=bool(row.get("majority_accepted")),
            affirmative_votes=int(row.get("affirmative_votes") or 0),
            dataset_accepted=bool(row.get("dataset_accepted")),
            acceptance_tau=float(row.get("acceptance_tau") or 4.0),
            validation_messages=row.get("validation_messages"),
            code_model="restored-live-snapshot",
            provider="mac-studio",
            created_at=created,
            updated_at=created,
        )
        session.add(artifact)
        session.flush()

        for score in row.get("scores") or []:
            session.add(
                ModelScore(
                    artifact_id=art_id,
                    model_key=str(score.get("model_key") or ""),
                    model_name=str(score.get("model_name") or ""),
                    score=int(score.get("score") or 0),
                    weight=float(score.get("weight") or 0.0),
                    available=bool(score.get("available", True)),
                    explanation=score.get("explanation"),
                    raw_output=score.get("raw_output"),
                    created_at=created,
                )
            )
        session.add(
            RenderAttempt(
                artifact_id=art_id,
                attempt_number=1,
                success=True,
                image_path=str(dest),
                fmt="png",
                created_at=created,
            )
        )
        session.add(
            CompositeScore(
                artifact_id=art_id,
                final_score=float(row.get("composite_score") or 0.0),
                majority_accepted=bool(row.get("majority_accepted")),
                affirmative_votes=int(row.get("affirmative_votes") or 0),
                dataset_accepted=bool(row.get("dataset_accepted")),
                tau=float(row.get("acceptance_tau") or 4.0),
                formula_snapshot="restored-live-snapshot",
                created_at=created,
            )
        )
        inserted.append(art_id)

    session.commit()
    return {"inserted": inserted, "skipped": skipped, "jobs_inserted": jobs_inserted}


def auto_import_gallery_history() -> dict[str, Any] | None:
    if not should_auto_import():
        return None
    from app.db import get_engine
    from app.settings import get_settings

    settings = get_settings()
    with Session(get_engine()) as session:
        result = import_gallery_history(session, artifact_dir=settings.artifact_dir)
    if result["inserted"]:
        logger.info(
            "Imported %s restored gallery diagrams: %s",
            len(result["inserted"]),
            result["inserted"],
        )
    return result
