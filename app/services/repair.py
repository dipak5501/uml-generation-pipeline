"""Adaptive repair: failure-category specific fixes, then LLM, then spec-builder."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.prompts_registry import render_prompt
from app.providers.factory import build_base_code_provider
from app.providers.mock_provider import MockProvider
from app.services.acceptance import (
    FAILURE_COMPILE,
    FAILURE_HALLUCINATION,
    FAILURE_MISSING,
    FAILURE_PACKAGE,
    FAILURE_RELATIONSHIP,
    FAILURE_RENDER,
    FAILURE_SEMANTIC,
    FAILURE_STRUCTURE,
    FAILURE_SYNTAX,
)
from app.services.plantuml_from_spec import plantuml_from_spec
from app.services.plantuml_validate import (
    ensure_plantuml_bounds,
    sanitize_plantuml_output,
    validate_diagram,
)
from app.settings import Settings, get_settings
from uml_pipeline.render import extract_plantuml_block

logger = logging.getLogger(__name__)


@dataclass
class RepairResult:
    code: str
    reason: str
    success_validation: bool
    messages: list[str]
    category: str = FAILURE_SYNTAX


def _spec_rebuild(spec_json: dict | None, specification: str, diagram_type: str) -> str:
    if spec_json:
        return sanitize_plantuml_output(plantuml_from_spec(spec_json, diagram_type))
    return sanitize_plantuml_output(
        MockProvider()._plantuml(  # noqa: SLF001
            f"Technical specification:\n{specification}",
            diagram_type,
        )
    )


def _close_braces(code: str) -> str:
    text = ensure_plantuml_bounds(code)
    opens = text.count("{")
    closes = text.count("}")
    if opens > closes:
        text = text.replace("@enduml", "") + ("\n}" * (opens - closes)) + "\n@enduml\n"
    return sanitize_plantuml_output(text)


def repair_plantuml(
    plantuml: str,
    specification: str,
    diagram_type: str,
    errors: list[str],
    repair_notes: str = "",
    settings: Settings | None = None,
    *,
    category: str | None = None,
    spec_json: dict | None = None,
) -> RepairResult:
    """Repair using previous failure information — never a blind regenerate."""
    settings = settings or get_settings()
    cat = (category or FAILURE_SYNTAX).strip() or FAILURE_SYNTAX
    errors = [e for e in (errors or []) if e]

    # 1) Deterministic, category-specific first
    if cat in {FAILURE_SYNTAX, FAILURE_COMPILE, FAILURE_STRUCTURE}:
        deterministic = _close_braces(sanitize_plantuml_output(ensure_plantuml_bounds(plantuml)))
        v = validate_diagram(deterministic, diagram_type)
        if v.ok:
            return RepairResult(
                code=deterministic,
                reason=f"deterministic {cat} repair (sanitize/braces)",
                success_validation=True,
                messages=v.messages,
                category=cat,
            )

    if cat in {
        FAILURE_MISSING,
        FAILURE_RELATIONSHIP,
        FAILURE_HALLUCINATION,
        FAILURE_PACKAGE,
        FAILURE_SEMANTIC,
        FAILURE_RENDER,
        FAILURE_STRUCTURE,
    }:
        rebuilt = _spec_rebuild(spec_json, specification, diagram_type)
        v = validate_diagram(rebuilt, diagram_type)
        if v.ok or cat in {FAILURE_MISSING, FAILURE_HALLUCINATION, FAILURE_PACKAGE, FAILURE_RELATIONSHIP}:
            return RepairResult(
                code=rebuilt,
                reason=f"spec-builder rebuild for {cat}: {'; '.join(errors[:2]) or 'n/a'}",
                success_validation=v.ok,
                messages=v.messages,
                category=cat,
            )

    # 2) Targeted LLM repair with the failure category + previous errors
    provider = build_base_code_provider(settings)
    ref, prompt = render_prompt(
        "repair_plantuml",
        "v1",
        diagram_type=diagram_type,
        specification=specification,
        plantuml=plantuml,
        errors="\n".join(errors) or "(none)",
        repair_notes=(repair_notes or "(none)") + f"\nfailure_category={cat}",
    )
    system = (
        f"You output only valid PlantUML for a {diagram_type} diagram. "
        f"Failure category: {cat}. Fix ONLY that class of error using the listed messages. "
        "Do not invent entities that are absent from the specification. "
        "Never convert to a different diagram type."
    )
    try:
        raw = provider.chat(system, prompt, temperature=0.1)
        fixed = sanitize_plantuml_output(ensure_plantuml_bounds(extract_plantuml_block(raw)))
    except Exception as exc:
        logger.warning("Repair provider failed (%s); using spec-builder/template", exc)
        fixed = _spec_rebuild(spec_json, specification, diagram_type)
        validation = validate_diagram(fixed, diagram_type)
        return RepairResult(
            code=fixed,
            reason=f"template/spec repair after provider error ({cat}): {exc}",
            success_validation=validation.ok,
            messages=validation.messages,
            category=cat,
        )

    validation = validate_diagram(fixed, diagram_type)
    if not validation.ok:
        rebuilt = _spec_rebuild(spec_json, specification, diagram_type)
        v2 = validate_diagram(rebuilt, diagram_type)
        return RepairResult(
            code=rebuilt,
            reason=f"spec-builder fallback after LLM {cat} repair via {ref.name}.{ref.version}",
            success_validation=v2.ok,
            messages=v2.messages,
            category=cat,
        )

    return RepairResult(
        code=fixed,
        reason=f"{cat} repair via {ref.name}.{ref.version}: {'; '.join(errors[:3])}",
        success_validation=validation.ok,
        messages=validation.messages,
        category=cat,
    )
