"""Repair / retry service for invalid PlantUML."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.prompts_registry import render_prompt
from app.providers.factory import build_code_provider
from app.services.plantuml_validate import ensure_plantuml_bounds, validate_diagram
from app.settings import Settings, get_settings
from uml_pipeline.render import extract_plantuml_block

logger = logging.getLogger(__name__)


@dataclass
class RepairResult:
    code: str
    reason: str
    success_validation: bool
    messages: list[str]


def repair_plantuml(
    plantuml: str,
    specification: str,
    diagram_type: str,
    errors: list[str],
    repair_notes: str = "",
    settings: Settings | None = None,
) -> RepairResult:
    settings = settings or get_settings()
    provider = build_code_provider(settings)
    ref, prompt = render_prompt(
        "repair_plantuml",
        "v1",
        diagram_type=diagram_type,
        specification=specification,
        plantuml=plantuml,
        errors="\n".join(errors) or "(none)",
        repair_notes=repair_notes or "(none)",
    )
    system = "You output only valid PlantUML. Never reveal private reasoning."
    try:
        raw = provider.chat(system, prompt, temperature=0.1)
    except Exception as exc:
        logger.exception("Repair provider failed")
        return RepairResult(code=plantuml, reason=f"provider error: {exc}", success_validation=False, messages=[str(exc)])

    fixed = ensure_plantuml_bounds(extract_plantuml_block(raw))
    validation = validate_diagram(fixed, diagram_type)
    return RepairResult(
        code=fixed,
        reason=f"repair via {ref.name}.{ref.version}: {'; '.join(errors[:3])}",
        success_validation=validation.ok,
        messages=validation.messages,
    )
