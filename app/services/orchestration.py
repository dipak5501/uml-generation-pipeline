"""End-to-end generation orchestration: requirement → artifact."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.models import (
    CompositeScore,
    GenerationJob,
    ModelScore,
    Project,
    RepairAttempt,
    RenderAttempt,
    RequirementInput,
    TechnicalSpecification,
    UMLArtifact,
)
from app.services.code_analysis import looks_like_source_code, structure_to_spec
from app.prompts_registry import diagram_prompt_name, render_prompt
from app.providers.factory import build_chat_provider, build_code_provider, build_vlm_providers
from app.services.cot import COT_SYSTEM, finalize_plantuml_output, has_cot_block
from app.services.plantuml_validate import ensure_plantuml_bounds, validate_diagram
from app.services.repair import repair_plantuml
from app.services.scoring import VerificationResult, paper_composite, verify_scores
from app.settings import Settings, get_settings
from uml_pipeline.render import render_plantuml

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_default_project(session: Session) -> Project:
    project = session.exec(select(Project).where(Project.name == "Thesis Demo")).first()
    if project is None:
        project = Project(name="Thesis Demo", description="Default thesis demonstration project")
        session.add(project)
        session.commit()
        session.refresh(project)
    return project


def generate_technical_spec(
    requirement: str,
    diagram_type: str,
    settings: Settings | None = None,
    input_mode: str = "requirement",
) -> tuple[str, str, str, str]:
    """Returns (spec_text, prompt_name, prompt_version, model_name)."""
    settings = settings or get_settings()
    mode = input_mode
    if mode == "requirement" and looks_like_source_code(requirement):
        mode = "source_code"

    provider = build_chat_provider(settings, model=settings.spec_model)
    if mode == "source_code":
        # Deterministic structural recover for mock/offline; LLM path uses prompt
        if settings.mock_providers:
            text = structure_to_spec(requirement, diagram_type)
            return text.strip(), "code_to_tech_spec", "v1", "mock-code-analysis"
        ref, prompt = render_prompt(
            "code_to_tech_spec",
            "v1",
            source_code=requirement,
            diagram_type=diagram_type,
        )
        system = "You are a senior software architect. Output only the technical specification recovered from code."
        text = provider.chat(system, prompt, temperature=0.2)
        model_name = getattr(provider, "model", settings.spec_model)
        return text.strip(), ref.name, ref.version, str(model_name)

    ref, prompt = render_prompt(
        "requirement_to_tech_spec",
        "v1",
        requirement=requirement,
        diagram_type=diagram_type,
    )
    system = "You are a senior system architect. Output only the technical specification."
    text = provider.chat(system, prompt, temperature=0.4)
    model_name = getattr(provider, "model", settings.spec_model)
    return text.strip(), ref.name, ref.version, str(model_name)


def generate_plantuml_code(
    specification: str,
    diagram_type: str,
    settings: Settings | None = None,
) -> tuple[str, str, str, str, bool]:
    """Returns (plantuml, prompt_name, prompt_version, model_name, used_cot)."""
    settings = settings or get_settings()
    provider = build_code_provider(settings)
    name = diagram_prompt_name(diagram_type)
    ref, prompt = render_prompt(name, "v1", specification=specification)
    system = COT_SYSTEM if settings.enable_cot else "You output only valid PlantUML code between @startuml and @enduml."
    raw = provider.chat(system, prompt, temperature=0.2)
    used_cot = has_cot_block(raw) or settings.enable_cot
    code = ensure_plantuml_bounds(finalize_plantuml_output(raw))
    model_name = getattr(provider, "model", settings.code_model)
    return code, ref.name, ref.version, str(model_name), used_cot


def score_image(
    image_path: Path,
    specification: str,
    settings: Settings | None = None,
) -> tuple[dict[str, int], dict[str, dict], float]:
    """Returns (scores, meta_by_key, composite)."""
    settings = settings or get_settings()
    weights = settings.vlm_weight_map
    providers = build_vlm_providers(settings)
    _, scoring_prompt = render_prompt("vlm_scoring", "v1", specification=specification)

    scores: dict[str, int] = {}
    meta: dict[str, dict] = {}
    for key, provider in providers.items():
        model_name = getattr(provider, "model", key)
        try:
            s = int(provider.vision_score(image_path, scoring_prompt))
            s = max(0, min(6, s))
            scores[key] = s
            meta[key] = {
                "model_name": str(model_name),
                "available": True,
                "explanation": None,
                "raw_output": str(s),
            }
        except Exception as exc:
            logger.warning("VLM %s unavailable: %s", key, exc)
            scores[key] = 0
            meta[key] = {
                "model_name": str(model_name),
                "available": False,
                "explanation": str(exc),
                "raw_output": None,
            }
    composite = paper_composite(scores, weights, render_ok=True)
    return scores, meta, composite


def apply_verification(
    artifact: UMLArtifact,
    scores: dict[str, int],
    meta: dict[str, dict],
    verification: VerificationResult,
    session: Session,
    *,
    clear_existing: bool = False,
) -> None:
    """Persist model scores + composite verification onto an artifact."""
    settings = get_settings()
    if clear_existing:
        for old in session.exec(select(ModelScore).where(ModelScore.artifact_id == artifact.id)).all():
            session.delete(old)
        for old in session.exec(
            select(CompositeScore).where(CompositeScore.artifact_id == artifact.id)
        ).all():
            session.delete(old)
        session.commit()

    artifact.composite_score = verification.composite
    artifact.majority_accepted = verification.majority_accepted
    artifact.affirmative_votes = verification.affirmative_votes
    artifact.dataset_accepted = verification.dataset_accepted
    artifact.acceptance_tau = verification.tau

    for key, weight in settings.vlm_weight_map.items():
        m = meta.get(key, {})
        session.add(
            ModelScore(
                artifact_id=artifact.id,
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
            artifact_id=artifact.id,
            final_score=verification.composite,
            majority_accepted=verification.majority_accepted,
            affirmative_votes=verification.affirmative_votes,
            dataset_accepted=verification.dataset_accepted,
            tau=verification.tau,
            formula_snapshot=verification.formula_snapshot,
        )
    )


def run_single_generation(
    session: Session,
    requirement: str,
    diagram_type: str,
    project_id: int | None = None,
    job_id: int | None = None,
    settings: Settings | None = None,
    input_mode: str = "requirement",
) -> UMLArtifact:
    settings = settings or get_settings()
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)

    if project_id is None:
        project = get_or_create_default_project(session)
        project_id = project.id
    assert project_id is not None

    resolved_mode = input_mode
    if resolved_mode == "requirement" and looks_like_source_code(requirement):
        resolved_mode = "source_code"

    req = RequirementInput(job_id=job_id, raw_text=requirement, diagram_type=diagram_type)
    session.add(req)
    session.commit()
    session.refresh(req)

    spec_text, spec_prompt, spec_ver, spec_model = generate_technical_spec(
        requirement, diagram_type, settings, input_mode=resolved_mode
    )
    tech = TechnicalSpecification(
        requirement_id=req.id,
        raw_text=spec_text,
        structured_json=json.dumps(
            {"diagram_type": diagram_type, "input_mode": resolved_mode}
        ),
        prompt_name=spec_prompt,
        prompt_version=spec_ver,
        model_name=spec_model,
        provider=settings.provider_name,
    )
    session.add(tech)
    session.commit()
    session.refresh(tech)

    plantuml, p_name, p_ver, code_model, used_cot = generate_plantuml_code(
        spec_text, diagram_type, settings
    )
    validation = validate_diagram(plantuml, diagram_type)
    validation_msgs = list(validation.messages)

    artifact = UMLArtifact(
        job_id=job_id,
        requirement_id=req.id,
        specification_id=tech.id,
        project_id=project_id,
        diagram_type=diagram_type,
        source_requirement=requirement,
        technical_spec=spec_text,
        plantuml_code=plantuml,
        render_status="pending",
        prompt_name=p_name,
        prompt_version=p_ver,
        code_model=code_model,
        provider=settings.provider_name,
        used_cot=used_cot,
        acceptance_tau=settings.acceptance_tau,
        validation_messages="\n".join(validation_msgs) if validation_msgs else None,
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)

    # Validate → repair loop before/during render
    jar = settings.plantuml_jar
    out_dir = settings.artifact_dir / str(artifact.id)
    out_dir.mkdir(parents=True, exist_ok=True)

    attempt = 0
    image_path: Path | None = None
    last_err: str | None = None
    repair_notes = ""

    while attempt <= settings.max_repair_attempts:
        # Static validation; force repair if package guards fail
        v = validate_diagram(artifact.plantuml_code, diagram_type)
        if not v.ok and attempt < settings.max_repair_attempts:
            repair = repair_plantuml(
                artifact.plantuml_code,
                spec_text,
                diagram_type,
                v.messages,
                repair_notes=repair_notes,
                settings=settings,
            )
            ra = RepairAttempt(
                artifact_id=artifact.id,
                attempt_number=attempt + 1,
                before_code=artifact.plantuml_code,
                after_code=repair.code,
                reason=repair.reason,
                success=repair.success_validation,
            )
            session.add(ra)
            artifact.plantuml_code = repair.code
            repair_notes += f"\n{repair.reason}"
            validation_msgs.extend(repair.messages)
            session.add(artifact)
            session.commit()
            attempt += 1
            continue

        img, err = render_plantuml(
            artifact.plantuml_code,
            out_dir,
            jar,
            fmt=settings.image_format,
        )
        last_err = err
        render_row = RenderAttempt(
            artifact_id=artifact.id,
            attempt_number=attempt + 1,
            success=img is not None,
            error_output=err,
            image_path=str(img) if img else None,
            fmt=settings.image_format,
        )
        session.add(render_row)
        session.commit()

        if img is not None:
            # Copy to stable name
            stable = out_dir / f"diagram.{settings.image_format}"
            if Path(img) != stable:
                shutil.copy2(img, stable)
            image_path = stable
            break

        # Environmental failures cannot be fixed by rewriting PlantUML
        env_fail = (err or "").lower()
        if "java" in env_fail or "runtime" in env_fail or "jdk" in env_fail:
            break

        if attempt >= settings.max_repair_attempts:
            break

        repair = repair_plantuml(
            artifact.plantuml_code,
            spec_text,
            diagram_type,
            [err or "render failed"],
            repair_notes=repair_notes,
            settings=settings,
        )
        ra = RepairAttempt(
            artifact_id=artifact.id,
            attempt_number=attempt + 1,
            before_code=artifact.plantuml_code,
            after_code=repair.code,
            reason=repair.reason,
            success=False,
        )
        session.add(ra)
        artifact.plantuml_code = repair.code
        repair_notes += f"\n{repair.reason}"
        session.add(artifact)
        session.commit()
        attempt += 1

    artifact.validation_messages = "\n".join(validation_msgs) if validation_msgs else artifact.validation_messages
    artifact.updated_at = _utcnow()

    scores: dict[str, int] = {k: 0 for k in settings.vlm_weight_map}
    meta: dict[str, dict] = {}

    if image_path is None:
        artifact.render_status = "failed"
        artifact.image_path = None
        for key in settings.vlm_weight_map:
            meta[key] = {
                "model_name": key,
                "available": True,
                "explanation": last_err or "render failed",
                "raw_output": None,
            }
        verification = verify_scores(
            scores,
            settings.vlm_weight_map,
            render_ok=False,
            tau=settings.acceptance_tau,
            min_composite=settings.min_composite_for_dataset,
        )
    else:
        artifact.render_status = "success"
        artifact.image_path = str(image_path)
        scores, meta, _ = score_image(image_path, spec_text, settings)
        verification = verify_scores(
            scores,
            settings.vlm_weight_map,
            render_ok=True,
            tau=settings.acceptance_tau,
            min_composite=settings.min_composite_for_dataset,
        )

    apply_verification(artifact, scores, meta, verification, session)
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


def create_job(session: Session, mode: str, total: int, project_id: int) -> GenerationJob:
    job = GenerationJob(project_id=project_id, mode=mode, status="pending", total=total, completed=0)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def update_job(session: Session, job: GenerationJob, **kwargs) -> GenerationJob:
    for k, v in kwargs.items():
        setattr(job, k, v)
    job.updated_at = _utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
