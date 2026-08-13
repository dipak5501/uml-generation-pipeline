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
from app.services.acceptance import (
    FAILURE_COMPILE,
    FAILURE_PACKAGE,
    FAILURE_RENDER,
    FAILURE_STRUCTURE,
    FAILURE_SYNTAX,
    evaluate_acceptance,
    write_acceptance_sidecar,
)
from app.services.plantuml_validate import ensure_plantuml_bounds, sanitize_plantuml_output, validate_diagram
from app.services.repair import repair_plantuml
from app.services.scoring import VerificationResult, paper_composite, verify_scores
from app.services.plantuml_from_spec import ensure_faithful_plantuml, plantuml_from_spec
from app.services.spec_json import ensure_valid_spec, validity_metrics
from app.settings import Settings, get_settings
from uml_pipeline.render import check_plantuml_syntax, render_plantuml

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

# Prefer LoRA for these when USE_FINETUNED_CODE=true (trained on real HF UMLCode data).
# Prefer LoRA for the four paper UML types; fall back to grounded builder if needed.
_LORA_PRIMARY_TYPES = frozenset({"class", "object", "component", "package"})


def _safe_template_plantuml(
    specification: str,
    diagram_type: str,
    spec_json: dict | None = None,
) -> str:
    """Deterministic last-resort diagram grounded in Stage-1 JSON when available."""
    from app.services.plantuml_from_spec import plantuml_from_spec
    from app.services.spec_json import ensure_valid_spec

    if spec_json:
        return plantuml_from_spec(spec_json, diagram_type)
    data, _, _ = ensure_valid_spec(specification, diagram_type)
    return plantuml_from_spec(data, diagram_type)


def _finetuned_output_needs_fallback(
    code: str,
    specification: str,
    validation_ok: bool,
    diagram_type: str = "class",
) -> bool:
    """Retry with base provider / builder when LoRA output is invalid or ignores the spec."""
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
    from app.services.input_prepare import (
        LLM_REQUIREMENT_CHARS,
        LLM_SOURCE_CODE_CHARS,
        clip_for_llm,
        is_long_input,
    )
    from app.services.spec_json import structure_to_spec_json

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
        # Structural analysis is reliable for full files; tiny LLMs choke on long code.
        grounded = structure_to_spec_json(requirement, diagram_type)
        use_structure = (
            settings.mock_providers
            or is_long_input(requirement)
            or grounded.get("script_without_types")
            or bool(grounded.get("entities"))
        )
        if use_structure:
            # ensure_valid_spec re-runs structure analysis from source_text
            spec_json, prose, msgs = ensure_valid_spec(
                "{}",
                diagram_type,
                source_text=requirement,
                input_mode="source_code",
            )
            # Optional LLM enrich only for short snippets when structure is sparse
            if (
                not settings.mock_providers
                and not grounded.get("script_without_types")
                and len(requirement) < 2500
                and len(spec_json.get("entities") or []) < 2
            ):
                ref, prompt = render_prompt(
                    "code_to_tech_spec",
                    "v1",
                    source_code=clip_for_llm(requirement, LLM_SOURCE_CODE_CHARS),
                    diagram_type=diagram_type,
                )
                try:
                    text = provider.chat(json_system, prompt, temperature=0.2)
                    spec_json, prose, msgs = ensure_valid_spec(
                        text.strip(),
                        diagram_type,
                        source_text=requirement,
                        input_mode="source_code",
                    )
                    model_name = getattr(provider, "model", settings.spec_model)
                    return prose, spec_json, ref.name, ref.version, str(model_name), msgs
                except Exception as exc:
                    logger.warning("Stage-1 LLM enrich failed; keeping structure: %s", exc)
            return prose, spec_json, "code_to_tech_spec", "v1", "code-structure", msgs

        ref, prompt = render_prompt(
            "code_to_tech_spec",
            "v1",
            source_code=clip_for_llm(requirement, LLM_SOURCE_CODE_CHARS),
            diagram_type=diagram_type,
        )
        text = provider.chat(json_system, prompt, temperature=0.2)
        model_name = getattr(provider, "model", settings.spec_model)
        spec_json, prose, msgs = ensure_valid_spec(
            text.strip(), diagram_type, source_text=requirement, input_mode="source_code"
        )
        return prose, spec_json, ref.name, ref.version, str(model_name), msgs

    llm_req = clip_for_llm(requirement, LLM_REQUIREMENT_CHARS)
    ref, prompt = render_prompt(
        "requirement_to_tech_spec",
        "v1",
        requirement=llm_req,
        diagram_type=diagram_type,
    )
    try:
        text = provider.chat(json_system, prompt, temperature=0.4)
    except Exception as exc:
        logger.warning("Stage-1 LLM failed (%s); recovering from text grounding", exc)
        spec_json, prose, msgs = ensure_valid_spec(
            "{}", diagram_type, source_text=requirement, input_mode="requirement"
        )
        return prose, spec_json, ref.name, ref.version, "grounded-fallback", msgs
    model_name = getattr(provider, "model", settings.spec_model)
    spec_json, prose, msgs = ensure_valid_spec(
        text.strip(), diagram_type, source_text=requirement, input_mode="requirement"
    )
    if msgs and any("not valid JSON" in m or "Missing required" in m for m in msgs):
        try:
            retry = provider.chat(
                json_system + " Retry: emit JSON only matching the required schema.",
                prompt,
                temperature=0.1,
            )
            spec_json, prose, msgs = ensure_valid_spec(
                retry.strip(), diagram_type, source_text=requirement, input_mode="requirement"
            )
        except Exception as exc:
            logger.warning("Stage-1 retry failed: %s", exc)
            spec_json, prose, msgs = ensure_valid_spec(
                "{}", diagram_type, source_text=requirement, input_mode="requirement"
            )
            model_name = "grounded-fallback"
    return prose, spec_json, ref.name, ref.version, str(model_name), msgs


def generate_plantuml_code(
    specification: str,
    diagram_type: str,
    settings: Settings | None = None,
    *,
    input_mode: str = "requirement",
    spec_json: dict | None = None,
) -> tuple[str, str, str, str, bool]:
    """Returns (plantuml, prompt_name, prompt_version, model_name, used_cot).

    When ``USE_FINETUNED_CODE=true``, prefer the LoRA model trained on the real
    Hugging Face UMLCode corpus; fall back to base LLM / grounded spec-builder
    if validation or fidelity checks fail.
    """
    from app.services.input_prepare import LORA_SPEC_CHARS, clip_for_llm

    settings = settings or get_settings()
    name = diagram_prompt_name(diagram_type)
    # Long specs overwhelm the 0.5B LoRA; clip for the model, keep full JSON for builder.
    spec_for_llm = clip_for_llm(specification, LORA_SPEC_CHARS)
    ref, prompt = render_prompt(name, "v1", specification=spec_for_llm)

    # Scripts with no class types: never invent classes via LoRA.
    if spec_json and spec_json.get("script_without_types"):
        code = plantuml_from_spec(spec_json, diagram_type)
        if validate_diagram(code, diagram_type).ok:
            return code, f"tech_spec_to_{diagram_type}", "v1", "spec-builder", False

    system = (
        COT_SYSTEM
        if settings.enable_cot
        else "You output only valid PlantUML code between @startuml and @enduml."
    )
    if diagram_type == "package":
        system = (
            "You output only valid PlantUML PACKAGE diagrams with nested "
            "package { } blocks and ..> dependencies. No self-dependencies. "
            "Use the exact package/entity names from the specification. "
            "Never invent Module1/Module2 placeholders."
        )
    elif diagram_type == "component":
        system = (
            "You output only valid PlantUML COMPONENT diagrams. "
            "Use the exact component names from the specification. "
            "Do not append extra Service suffixes. Never invent ModuleN names."
        )
    else:
        system = (
            system
            + " Use exact entity names from the specification. "
            "Never invent ModuleN/EntityA placeholders. "
            "Use --|> only for true inheritance; otherwise use --> *-- o-- or ..>."
        )

    use_lora = settings.use_finetuned_code and diagram_type in _LORA_PRIMARY_TYPES
    code = ""
    used_cot = False
    model_name = "spec-builder"
    validation = validate_diagram("@startuml\n@enduml\n", diagram_type)

    if use_lora:
        provider = build_code_provider(settings)
        raw = ""
        try:
            raw = provider.chat(system, prompt, temperature=0.2)
        except Exception as exc:
            logger.warning("Fine-tuned code provider failed (%s); falling back", exc)
        if raw:
            used_cot = has_cot_block(raw) or settings.enable_cot
            code = sanitize_plantuml_output(finalize_plantuml_output(raw))
            validation = validate_diagram(code, diagram_type)
            model_name = str(getattr(provider, "model", "finetuned-mlx"))
            if not _finetuned_output_needs_fallback(
                code, specification, validation.ok, diagram_type
            ):
                if spec_json:
                    code, fidelity = ensure_faithful_plantuml(code, spec_json, diagram_type)
                    if fidelity.get("replaced"):
                        model_name = "spec-builder"
                        used_cot = False
                return code, ref.name, ref.version, model_name, used_cot
            logger.warning(
                "LoRA PlantUML weak for %s; trying base provider / spec-builder",
                diagram_type,
            )
            fallback = build_base_code_provider(settings)
            try:
                raw_fb = fallback.chat(system, prompt, temperature=0.2)
                code_fb = sanitize_plantuml_output(finalize_plantuml_output(raw_fb))
                validation_fb = validate_diagram(code_fb, diagram_type)
                if validation_fb.ok and not _finetuned_output_needs_fallback(
                    code_fb, specification, True, diagram_type
                ):
                    code, validation, used_cot = (
                        code_fb,
                        validation_fb,
                        has_cot_block(raw_fb) or used_cot,
                    )
                    model_name = str(getattr(fallback, "model", settings.code_model))
                elif validation_fb.ok or (not validation.ok and len(code_fb) >= 20):
                    code, validation, used_cot = (
                        code_fb,
                        validation_fb,
                        has_cot_block(raw_fb) or used_cot,
                    )
                    model_name = str(getattr(fallback, "model", settings.code_model))
            except Exception as exc:
                logger.warning("Base code fallback failed: %s", exc)

    elif settings.mock_providers:
        provider = build_code_provider(settings)
        try:
            raw = provider.chat(system, prompt, temperature=0.2)
            used_cot = has_cot_block(raw) or settings.enable_cot
            code = sanitize_plantuml_output(finalize_plantuml_output(raw))
            validation = validate_diagram(code, diagram_type)
            model_name = str(getattr(provider, "model", "mock"))
        except Exception as exc:
            logger.warning("Mock code provider failed: %s", exc)
    else:
        provider = build_chat_provider(settings, model=settings.code_model)
        try:
            raw = provider.chat(system, prompt, temperature=0.2)
            used_cot = has_cot_block(raw) or settings.enable_cot
            code = sanitize_plantuml_output(finalize_plantuml_output(raw))
            validation = validate_diagram(code, diagram_type)
            model_name = str(getattr(provider, "model", settings.code_model))
        except Exception as exc:
            logger.warning("Code provider failed (%s); using template", exc)
            code = _safe_template_plantuml(specification, diagram_type, spec_json)
            return code, ref.name, ref.version, "template-fallback", False

    # Grounded builder when model path failed or was skipped
    if (not code or not validation.ok) and spec_json:
        built = plantuml_from_spec(spec_json, diagram_type)
        if validate_diagram(built, diagram_type).ok:
            code, model_name, used_cot = built, "spec-builder", False
            validation = validate_diagram(code, diagram_type)

    if not validation.ok:
        logger.warning(
            "PlantUML for %s still invalid after model attempts (%s); using safe template",
            diagram_type,
            "; ".join(validation.messages[:3]),
        )
        code = _safe_template_plantuml(specification, diagram_type, spec_json)
        model_name = "template-fallback"
        used_cot = False

    # Professional fidelity gate: diagram must cover Stage-1 entities
    if spec_json:
        code, fidelity = ensure_faithful_plantuml(code, spec_json, diagram_type)
        if fidelity.get("replaced"):
            logger.warning(
                "Replaced model PlantUML with spec-builder (recall=%.2f missing=%s generics=%s)",
                float(fidelity.get("prior", {}).get("recall") or 0),
                fidelity.get("prior", {}).get("missing"),
                fidelity.get("prior", {}).get("generic_placeholders"),
            )
            model_name = "spec-builder"
            used_cot = False

    return code, ref.name, ref.version, str(model_name), used_cot



def score_image(
    image_path: Path,
    specification: str,
    settings: Settings | None = None,
) -> tuple[dict[str, int | None], dict[str, dict], float]:
    """Returns (scores, meta_by_key, composite)."""
    settings = settings or get_settings()
    weights = settings.vlm_weight_map
    providers = build_vlm_providers(settings)
    # Fast mode: first available VLM only (demos / weak machines). Full ensemble for thesis.
    if settings.vlm_fast_mode and providers:
        first_key = next(iter(providers))
        providers = {first_key: providers[first_key]}
    _, scoring_prompt = render_prompt("vlm_scoring", "v1", specification=specification)

    scores: dict[str, int | None] = {}
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
    # Mark skipped ensemble members as unavailable (None) so they do not drag S to 0
    for key in weights:
        if key not in scores:
            scores[key] = None
            meta[key] = {
                "model_name": key,
                "available": False,
                "explanation": "skipped (VLM_FAST_MODE)",
                "raw_output": None,
            }
    composite = paper_composite(scores, weights, render_ok=True)
    return scores, meta, composite


def apply_verification(
    artifact: UMLArtifact,
    scores: dict[str, int | None],
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
        raw_score = scores.get(key, 0)
        session.add(
            ModelScore(
                artifact_id=artifact.id,
                model_key=key,
                model_name=str(m.get("model_name", key)),
                score=0 if raw_score is None else int(raw_score),
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

    # Source scripts with no class declarations must not invent fake classes
    if isinstance(spec_json, dict) and spec_json.get("script_without_types"):
        validation_note = (
            "Source has no class declarations; avoided inventing classes from variables."
        )
    else:
        validation_note = ""

    plantuml, p_name, p_ver, code_model, used_cot = generate_plantuml_code(
        spec_text,
        diagram_type,
        settings,
        input_mode=resolved_mode,
        spec_json=spec_json,
    )
    validation = validate_diagram(plantuml, diagram_type)
    validation_msgs = list(validation.messages)
    if validation_note:
        validation_msgs.insert(0, validation_note)

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

    # Multi-layer gates: syntax → compile → render → UML rules → semantics
    jar = settings.plantuml_jar
    out_dir = settings.artifact_dir / str(artifact.id)
    out_dir.mkdir(parents=True, exist_ok=True)

    attempt = 0
    image_path: Path | None = None
    last_err: str | None = None
    repair_notes = ""
    last_category = FAILURE_SYNTAX

    def _apply_repair(errors: list[str], category: str) -> None:
        nonlocal attempt, repair_notes, last_category
        last_category = category
        repair = repair_plantuml(
            artifact.plantuml_code,
            spec_text,
            diagram_type,
            errors,
            repair_notes=repair_notes,
            settings=settings,
            category=category,
            spec_json=spec_json,
        )
        session.add(
            RepairAttempt(
                artifact_id=artifact.id,
                attempt_number=attempt + 1,
                before_code=artifact.plantuml_code,
                after_code=repair.code,
                reason=repair.reason,
                success=repair.success_validation,
            )
        )
        artifact.plantuml_code = repair.code
        repair_notes += f"\n[{category}] {repair.reason}"
        validation_msgs.extend(repair.messages)
        session.add(artifact)
        session.commit()
        attempt += 1

    while attempt <= settings.max_repair_attempts:
        v = validate_diagram(artifact.plantuml_code, diagram_type)
        if not v.ok and attempt < settings.max_repair_attempts:
            joined = " ".join(v.messages).lower()
            if "package" in joined or "nested" in joined or "containment" in joined:
                cat = FAILURE_PACKAGE
            elif any(k in joined for k in ("class", "component", "object", "relationship", "duplicate")):
                cat = FAILURE_STRUCTURE
            else:
                cat = FAILURE_SYNTAX
            _apply_repair(v.messages, cat)
            continue

        compile_ok, compile_err = check_plantuml_syntax(
            artifact.plantuml_code, jar, work_dir=out_dir / "syntax"
        )
        if not compile_ok and attempt < settings.max_repair_attempts:
            _apply_repair([compile_err or "PlantUML compile failed"], FAILURE_COMPILE)
            continue

        img, err = render_plantuml(
            artifact.plantuml_code,
            out_dir,
            jar,
            fmt=settings.image_format,
        )
        last_err = err
        session.add(
            RenderAttempt(
                artifact_id=artifact.id,
                attempt_number=attempt + 1,
                success=img is not None,
                error_output=err,
                image_path=str(img) if img else None,
                fmt=settings.image_format,
            )
        )
        session.commit()

        if img is None:
            env_fail = (err or "").lower()
            if "java" in env_fail or "runtime" in env_fail or "jdk" in env_fail:
                break
            if attempt >= settings.max_repair_attempts:
                break
            _apply_repair([err or "render failed"], FAILURE_RENDER)
            continue

        stable = out_dir / f"diagram.{settings.image_format}"
        if Path(img) != stable:
            shutil.copy2(img, stable)
        image_path = stable

        report = evaluate_acceptance(
            requirement=requirement,
            plantuml=artifact.plantuml_code,
            diagram_type=diagram_type,
            spec=spec_json,
            render_ok=True,
            repair_iterations=attempt,
        )
        if report.accepted:
            break
        if attempt >= settings.max_repair_attempts:
            break
        msgs = []
        for g in report.gates:
            if not g.ok:
                msgs.extend(g.messages or [g.name])
        _apply_repair(msgs or [report.failure_category or "semantic"], report.failure_category or FAILURE_SYNTAX)
        image_path = None

    # Last resort: deterministic template if still not renderable
    if image_path is None:
        safe = _safe_template_plantuml(spec_text, diagram_type, spec_json)
        if safe.strip() and safe.strip() != (artifact.plantuml_code or "").strip():
            img, err = render_plantuml(safe, out_dir, jar, fmt=settings.image_format)
            session.add(
                RepairAttempt(
                    artifact_id=artifact.id,
                    attempt_number=attempt + 1,
                    before_code=artifact.plantuml_code,
                    after_code=safe,
                    reason=f"safe template fallback after render failure: {last_err or err or 'n/a'}",
                    success=img is not None,
                )
            )
            artifact.plantuml_code = safe
            if img is not None:
                stable = out_dir / f"diagram.{settings.image_format}"
                if Path(img) != stable:
                    shutil.copy2(img, stable)
                image_path = stable
                last_err = None
            else:
                last_err = err or last_err
            session.add(artifact)
            session.commit()

    final_report = evaluate_acceptance(
        requirement=requirement,
        plantuml=artifact.plantuml_code,
        diagram_type=diagram_type,
        spec=spec_json,
        render_ok=image_path is not None,
        repair_iterations=attempt,
    )
    write_acceptance_sidecar(out_dir, final_report)
    validation_msgs.extend(final_report.summary_lines())
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
            min_votes=1 if settings.vlm_fast_mode else 2,
        )

    apply_verification(artifact, scores, meta, verification, session)
    if not final_report.accepted:
        artifact.dataset_accepted = False
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
