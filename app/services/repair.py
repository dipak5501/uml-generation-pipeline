"""Repair / retry service for invalid PlantUML."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.prompts_registry import render_prompt
from app.providers.factory import build_base_code_provider
from app.providers.mock_provider import MockProvider
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


def repair_plantuml(
    plantuml: str,
    specification: str,
    diagram_type: str,
    errors: list[str],
    repair_notes: str = "",
    settings: Settings | None = None,
) -> RepairResult:
    settings = settings or get_settings()
    # Prefer base/spec model — LoRA often rewrites package/flowchart into class UML.
    provider = build_base_code_provider(settings)
    ref, prompt = render_prompt(
        "repair_plantuml",
        "v1",
        diagram_type=diagram_type,
        specification=specification,
        plantuml=plantuml,
        errors="\n".join(errors) or "(none)",
        repair_notes=repair_notes or "(none)",
    )
    system = (
        f"You output only valid PlantUML for a {diagram_type} diagram. "
        "Never reveal private reasoning. Never convert to a class diagram "
        "unless the requested type is class."
    )
    try:
        raw = provider.chat(system, prompt, temperature=0.1)
        fixed = sanitize_plantuml_output(ensure_plantuml_bounds(extract_plantuml_block(raw)))
    except Exception as exc:
        logger.warning("Repair provider failed (%s); using template", exc)
        fixed = sanitize_plantuml_output(
            MockProvider()._plantuml(  # noqa: SLF001
                f"Technical specification:\n{specification}",
                diagram_type,
            )
        )
        validation = validate_diagram(fixed, diagram_type)
        return RepairResult(
            code=fixed,
            reason=f"template repair after provider error: {exc}",
            success_validation=validation.ok,
            messages=validation.messages,
        )

    validation = validate_diagram(fixed, diagram_type)
    if not validation.ok and diagram_type in {"package", "flowchart"}:
        fixed = sanitize_plantuml_output(
            MockProvider()._plantuml(  # noqa: SLF001
                f"Technical specification:\n{specification}",
                diagram_type,
            )
        )
        validation = validate_diagram(fixed, diagram_type)
        return RepairResult(
            code=fixed,
            reason=f"template repair via {ref.name}.{ref.version}: {'; '.join(errors[:3])}",
            success_validation=validation.ok,
            messages=validation.messages,
        )

    return RepairResult(
        code=fixed,
        reason=f"repair via {ref.name}.{ref.version}: {'; '.join(errors[:3])}",
        success_validation=validation.ok,
        messages=validation.messages,
    )
