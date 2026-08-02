"""End-to-end generation orchestration: requirement → artifact."""

from __future__ import annotations

import json
import logging
import re
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
from app.services.code_analysis import (
    detect_source_language,
    looks_like_source_code,
    resolve_input_mode,
    structure_to_spec,
)
from app.prompts_registry import diagram_prompt_name, render_prompt
from app.providers.factory import (
    build_base_code_provider,
    build_chat_provider,
    build_code_provider,
    build_vlm_providers,
)
from app.services.cot import COT_SYSTEM, finalize_plantuml_output, has_cot_block
from app.services.plantuml_validate import ensure_plantuml_bounds, sanitize_plantuml_output, validate_diagram
from app.services.repair import repair_plantuml
from app.services.scoring import VerificationResult, paper_composite, verify_scores
from app.services.spec_json import ensure_valid_spec, validity_metrics
from app.settings import Settings, get_settings
from uml_pipeline.render import render_plantuml

logger = logging.getLogger(__name__)

_GENERIC_CLASS_NAMES = {
    "entity",
    "entities",
    "detected",
    "language",
    "unknown",
    "model",
    "class",
    "process",
    "module",
    "module1",
    "module2",
}

# LoRA corpus is mostly class-style UML; these types need the base/mock generators.
_LORA_SKIP_TYPES = frozenset({"package", "flowchart"})


def _safe_template_plantuml(specification: str, diagram_type: str) -> str:
    """Deterministic last-resort diagram when models produce wrong/broken PlantUML."""
    from app.providers.mock_provider import MockProvider

    return sanitize_plantuml_output(
        MockProvider()._plantuml(  # noqa: SLF001 — intentional template reuse
            f"Technical specification:\n{specification}",
            diagram_type,
        )
    )


def _finetuned_output_needs_fallback(
    code: str,
    specification: str,
    validation_ok: bool,
    diagram_type: str = "class",
) -> bool:
    """Retry with mock/base provider when LoRA output is invalid or ignores the spec."""
    if diagram_type in _LORA_SKIP_TYPES:
        return True
    if not validation_ok:
        return True
    classes = re.findall(r"(?m)^\s*class\s+(\w+)", code, flags=re.I)
    if classes and all(c.lower() in _GENERIC_CLASS_NAMES for c in classes):
        return True
    spec_entities = re.findall(r"(?m)^-\s*([A-Za-z_]\w*)\s*:", specification)
    if spec_entities:
        code_lower = code.lower()
        if not any(ent.lower() in code_lower for ent in spec_entities[:8]):
            return True
    return False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_default_project(session: Session) -> Project:
    project = session.exec(select(Project).where(Project.name == "UML-Pipeline")).first()
    if project is None:
        legacy = session.exec(select(Project).where(Project.name == "Thesis Demo")).first()
        if legacy is not None:
            legacy.name = "UML-Pipeline"
            legacy.description = "Default UML-Pipeline project"
            session.add(legacy)
            session.commit()
            session.refresh(legacy)
            return legacy
        project = Project(name="UML-Pipeline", description="Default UML-Pipeline project")
        session.add(project)
        session.commit()
        session.refresh(project)
    return project


def generate_technical_spec(
    requirement: str,
    diagram_type: str,
    settings: Settings | None = None,
    input_mode: str = "requirement",
) -> tuple[str, dict, str, str, str, list[str]]:
    """Returns (spec_prose, spec_json, prompt_name, prompt_version, model_name, validity_msgs)."""
    settings = settings or get_settings()
    mode = input_mode
    if mode == "requirement" and looks_like_source_code(requirement):
        mode = "source_code"

    provider = build_chat_provider(settings, model=settings.spec_model)
    json_system = (
        "You are a senior system architect. Output ONLY one valid JSON object for the "
        "Stage-1 technical specification. No markdown fences or prose outside JSON."
    )
    if mode == "source_code":
        # Deterministic structural recover for mock/offline; LLM path uses prompt
        if settings.mock_providers:
            text = structure_to_spec(requirement, diagram_type)
            spec_json, prose, msgs = ensure_valid_spec(text, diagram_type)
            return prose, spec_json, "code_to_tech_spec", "v1", "mock-code-analysis", msgs
        ref, prompt = render_prompt(
            "code_to_tech_spec",
            "v1",
            source_code=requirement,
            diagram_type=diagram_type,
        )
        text = provider.chat(json_system, prompt, temperature=0.2)
        model_name = getattr(provider, "model", settings.spec_model)
        spec_json, prose, msgs = ensure_valid_spec(text.strip(), diagram_type)
        if msgs and "not valid JSON" in " ".join(msgs):
            # One retry emphasizing JSON-only
            retry = provider.chat(
                json_system + " Retry: emit JSON only matching the required schema.",
                prompt,
                temperature=0.1,
            )
            spec_json, prose, msgs = ensure_valid_spec(retry.strip(), diagram_type)
        return prose, spec_json, ref.name, ref.version, str(model_name), msgs

    ref, prompt = render_prompt(
        "requirement_to_tech_spec",
        "v1",
        requirement=requirement,
        diagram_type=diagram_type,
    )
    text = provider.chat(json_system, prompt, temperature=0.4)
    model_name = getattr(provider, "model", settings.spec_model)
    spec_json, prose, msgs = ensure_valid_spec(text.strip(), diagram_type)
    if msgs and any("not valid JSON" in m or "Missing required" in m for m in msgs):
        retry = provider.chat(
            json_system + " Retry: emit JSON only matching the required schema.",
            prompt,
            temperature=0.1,
        )
        spec_json, prose, msgs = ensure_valid_spec(retry.strip(), diagram_type)
    return prose, spec_json, ref.name, ref.version, str(model_name), msgs


def generate_plantuml_code(
    specification: str,
    diagram_type: str,
    settings: Settings | None = None,
    *,
    input_mode: str = "requirement",
) -> tuple[str, str, str, str, bool]:
    """Returns (plantuml, prompt_name, prompt_version, model_name, used_cot)."""
    settings = settings or get_settings()
    # LoRA was trained mainly on class UML; package/flowchart + source-code use base provider.
    if input_mode == "source_code" or diagram_type in _LORA_SKIP_TYPES:
        provider = build_base_code_provider(settings)
    else:
        provider = build_code_provider(settings)
    name = diagram_prompt_name(diagram_type)
    ref, prompt = render_prompt(name, "v1", specification=specification)
    system = COT_SYSTEM if settings.enable_cot else "You output only valid PlantUML code between @startuml and @enduml."
    if diagram_type == "flowchart":
        system = (
            "You output only valid PlantUML ACTIVITY/FLOWCHART syntax using "
            "start, :Step;, if/else/endif, and stop. Do NOT emit class diagrams."
        )
    elif diagram_type == "package":
        system = (
            "You output only valid PlantUML PACKAGE diagrams with nested "
            "package { } blocks and ..> dependencies. No self-dependencies."
        )
    try:
        raw = provider.chat(system, prompt, temperature=0.2)
    except Exception as exc:
        logger.warning("Code provider failed (%s); using base fallback", exc)
        provider = build_base_code_provider(settings)
        try:
            raw = provider.chat(system, prompt, temperature=0.2)
        except Exception as exc2:
            logger.warning("Base code provider failed (%s); using template", exc2)
            code = _safe_template_plantuml(specification, diagram_type)
            return code, ref.name, ref.version, "template-fallback", False
    used_cot = has_cot_block(raw) or settings.enable_cot
    code = sanitize_plantuml_output(finalize_plantuml_output(raw))
    validation = validate_diagram(code, diagram_type)
    if settings.use_finetuned_code and getattr(provider, "name", "") == "finetuned-mlx" and _finetuned_output_needs_fallback(
        code, specification, validation.ok, diagram_type
    ):
        reason = "invalid syntax" if not validation.ok else "generic or spec-mismatched output"
        logger.warning(
            "Fine-tuned code model produced weak %s PlantUML (%s); retrying with base provider: %s",
            diagram_type,
            reason,
            ", ".join(validation.messages) if validation.messages else "n/a",
        )
        fallback = build_base_code_provider(settings)
        try:
            raw_fb = fallback.chat(system, prompt, temperature=0.2)
        except Exception as exc:
            logger.warning("Base code fallback also failed: %s", exc)
            raw_fb = raw
        code_fb = sanitize_plantuml_output(finalize_plantuml_output(raw_fb))
        validation_fb = validate_diagram(code_fb, diagram_type)
        if validation_fb.ok or (not validation.ok and len(code_fb) >= 20):
            code = code_fb
            used_cot = has_cot_block(raw_fb) or used_cot
            provider = fallback
            validation = validation_fb

    # Last resort: deterministic typed template (fixes LoRA/Ollama class-as-flowchart failures)
    if not validation.ok:
        logger.warning(
            "PlantUML for %s still invalid after model attempts (%s); using safe template",
            diagram_type,
            "; ".join(validation.messages[:3]),
        )
        code = _safe_template_plantuml(specification, diagram_type)
        return code, ref.name, ref.version, "template-fallback", used_cot

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
            if hasattr(provider, "vision_assess"):
                assessment = provider.vision_assess(image_path, scoring_prompt)
                s = int(assessment.score)
                explanation = assessment.explanation
                raw_output = assessment.raw_output
            else:
                s = int(provider.vision_score(image_path, scoring_prompt))
                explanation = None
                raw_output = str(s)
            s = max(0, min(6, s))
            scores[key] = s
            meta[key] = {
                "model_name": str(model_name),
                "available": True,
                "explanation": explanation,
                "raw_output": raw_output,
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

    resolved_mode = resolve_input_mode(requirement, input_mode)
    source_language = detect_source_language(requirement, input_mode)

    req = RequirementInput(job_id=job_id, raw_text=requirement, diagram_type=diagram_type)
    session.add(req)
    session.commit()
    session.refresh(req)

    spec_text, spec_json, spec_prompt, spec_ver, spec_model, spec_msgs = generate_technical_spec(
        requirement, diagram_type, settings, input_mode=resolved_mode
    )
    if spec_msgs:
        logger.info("Stage-1 JSON validity notes: %s", "; ".join(spec_msgs[:4]))
    tech = TechnicalSpecification(
        requirement_id=req.id,
        raw_text=spec_text,
        structured_json=json.dumps(
            {
                "diagram_type": diagram_type,
                "input_mode": resolved_mode,
                "spec": spec_json,
                "validity": validity_metrics(spec_json),
                "validity_messages": spec_msgs,
            },
            ensure_ascii=False,
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
        spec_text, diagram_type, settings, input_mode=resolved_mode
    )
    validation = validate_diagram(plantuml, diagram_type)
    validation_msgs = list(validation.messages)

    artifact = UMLArtifact(
        job_id=job_id,
        requirement_id=req.id,
        specification_id=tech.id,
        project_id=project_id,
        diagram_type=diagram_type,
        input_mode=resolved_mode,
        source_language=source_language,
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
