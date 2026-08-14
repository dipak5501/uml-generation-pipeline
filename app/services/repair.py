"""Category-specific PlantUML repair, ordered by self-adaptation memory."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from app.prompts_registry import render_prompt
from app.providers.factory import build_base_code_provider
from app.providers.mock_provider import MockProvider
from app.services.acceptance import FAILURE_SYNTAX
from app.services.adaptation import AdaptationMemory, choose_strategies
from app.services.plantuml_from_spec import plantuml_from_spec
from app.services.plantuml_validate import (
    ensure_plantuml_bounds,
    sanitize_plantuml_output,
    validate_diagram,
)
from app.services.traceability import expected_from_requirement
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
    strategy: str = "spec_rebuild"


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


def strategy_sanitize_syntax(code: str, **_: Any) -> str:
    return _close_braces(sanitize_plantuml_output(ensure_plantuml_bounds(code)))


def strategy_spec_rebuild(
    code: str,
    *,
    spec_json: dict | None,
    specification: str,
    diagram_type: str,
    **_: Any,
) -> str:
    return _spec_rebuild(spec_json, specification, diagram_type)


def strategy_inject_missing(
    code: str,
    *,
    spec_json: dict | None,
    specification: str,
    diagram_type: str,
    errors: list[str],
    **_: Any,
) -> str:
    required = expected_from_requirement(specification, spec_json)
    text = ensure_plantuml_bounds(code)
    low = text.lower()
    missing = [n for n in required if n.lower() not in low]
    if not missing:
        return _spec_rebuild(spec_json, specification, diagram_type)
    if len(missing) >= max(3, len(required) // 2):
        return _spec_rebuild(spec_json, specification, diagram_type)
    lines = []
    for name in missing:
        if diagram_type == "package":
            lines.append(f"package {name} {{\n  class {name}\n}}")
        elif diagram_type == "component":
            lines.append(f"[{name}] as {name}")
        elif diagram_type == "object":
            lines.append(f'object "{name}1 : {name}" as {name}1')
        else:
            lines.append(f"class {name}")
    if len(missing) >= 2:
        a, b = missing[0], missing[1]
        if diagram_type == "package":
            lines.append(f"{a} ..> {b}")
        else:
            lines.append(f"{a} --> {b}")
    injected = text.replace("@enduml", "\n".join(lines) + "\n@enduml", 1)
    return sanitize_plantuml_output(injected)


def strategy_strip_hallucinations(
    code: str,
    *,
    spec_json: dict | None,
    specification: str,
    **_: Any,
) -> str:
    keep = {n.lower() for n in expected_from_requirement(specification, spec_json)}
    if not keep:
        return sanitize_plantuml_output(ensure_plantuml_bounds(code))
    text = ensure_plantuml_bounds(code)
    drop: list[str] = []
    for m in re.finditer(
        r"(?im)^\s*(?:abstract\s+)?(?:class|interface|enum|package|object|component)\s+"
        r"(?:\"([^\"]+)\"\s+as\s+)?([A-Za-z_][\w]*)",
        text,
    ):
        name = (m.group(2) or m.group(1) or "").strip()
        if name and name.lower() not in keep and not any(name.lower().startswith(k) for k in keep):
            drop.append(name)
    for m in re.finditer(r"(?im)^\s*\[([^\]]+)\]", text):
        raw = re.sub(r"\s+as\s+\S+$", "", m.group(1)).strip()
        token = re.sub(r"[^\w]", "_", raw.split()[0]) if raw else ""
        if token and token.lower() not in keep:
            drop.append(token)
    out = text
    for name in dict.fromkeys(drop):
        out = re.sub(
            rf"(?ims)^\s*(?:abstract\s+)?class\s+{re.escape(name)}\b[^\n]*\{{.*?^\s*\}}\s*\n",
            "",
            out,
        )
        out = re.sub(rf"(?im)^\s*(?:abstract\s+)?(?:class|interface|enum|package|object)\s+{re.escape(name)}\b[^\n]*\n", "", out)
        out = re.sub(rf"(?im)^\s*package\s+{re.escape(name)}\s*\{{[\s\S]*?^\}}\s*\n", "", out)
        out = re.sub(rf"(?im)^.*\b{re.escape(name)}\b.*(?:-->|\.\.>|\*--|o--|--\|>|\+\-\-).*\n", "", out)
    return sanitize_plantuml_output(out)


def strategy_fix_relationships(
    code: str,
    *,
    spec_json: dict | None,
    specification: str,
    diagram_type: str,
    **_: Any,
) -> str:
    rebuilt = _spec_rebuild(spec_json, specification, diagram_type)
    # Keep existing type declarations; replace only connector lines from the spec builder.
    decls = [
        ln
        for ln in ensure_plantuml_bounds(code).splitlines()
        if not re.search(r"(-->|\.\.>|\*--|o--|--\|>|<\|--|..\|>|\+\-\-)", ln)
        and ln.strip().lower() not in {"@startuml", "@enduml"}
        and not ln.strip().lower().startswith("title ")
    ]
    rels = [
        ln
        for ln in rebuilt.splitlines()
        if re.search(r"(-->|\.\.>|\*--|o--|--\|>|<\|--|..\|>|\+\-\-)", ln)
    ]
    if not decls:
        return rebuilt
    lines = ["@startuml", *decls, *rels, "@enduml"]
    return sanitize_plantuml_output("\n".join(lines) + "\n")


def strategy_fix_package_hierarchy(
    code: str,
    *,
    spec_json: dict | None,
    specification: str,
    diagram_type: str,
    **_: Any,
) -> str:
    return _spec_rebuild(spec_json, specification, "package" if diagram_type == "package" else diagram_type)


def strategy_llm_targeted(
    code: str,
    *,
    specification: str,
    diagram_type: str,
    errors: list[str],
    repair_notes: str,
    category: str,
    settings: Settings,
    spec_json: dict | None,
    **_: Any,
) -> str:
    provider = build_base_code_provider(settings)
    ref, prompt = render_prompt(
        "repair_plantuml",
        "v1",
        diagram_type=diagram_type,
        specification=specification,
        plantuml=code,
        errors="\n".join(errors) or "(none)",
        repair_notes=(repair_notes or "(none)") + f"\nfailure_category={category}",
    )
    system = (
        f"You output only valid PlantUML for a {diagram_type} diagram. "
        f"Failure category: {category}. Fix ONLY that class of error using the listed messages. "
        "Do not invent entities that are absent from the specification. "
        "Never convert to a different diagram type."
    )
    try:
        raw = provider.chat(system, prompt, temperature=0.1)
        return sanitize_plantuml_output(ensure_plantuml_bounds(extract_plantuml_block(raw)))
    except Exception as exc:
        logger.warning("Targeted LLM repair failed (%s)", exc)
        return _spec_rebuild(spec_json, specification, diagram_type)


_STRATEGIES: dict[str, Callable[..., str]] = {
    "sanitize_syntax": strategy_sanitize_syntax,
    "spec_rebuild": strategy_spec_rebuild,
    "inject_missing": strategy_inject_missing,
    "strip_hallucinations": strategy_strip_hallucinations,
    "fix_relationships": strategy_fix_relationships,
    "fix_package_hierarchy": strategy_fix_package_hierarchy,
    "llm_targeted": strategy_llm_targeted,
}


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
    tried: list[str] | None = None,
    memory: AdaptationMemory | None = None,
) -> RepairResult:
    """Run the next unused strategy for this failure category (not a blind regenerate)."""
    settings = settings or get_settings()
    cat = (category or FAILURE_SYNTAX).strip() or FAILURE_SYNTAX
    errors = [e for e in (errors or []) if e]
    memory = memory or AdaptationMemory()
    order = choose_strategies(diagram_type, cat, tried=tried, memory=memory)
    if not order:
        order = ["spec_rebuild"]

    kwargs = {
        "spec_json": spec_json,
        "specification": specification,
        "diagram_type": diagram_type,
        "errors": errors,
        "repair_notes": repair_notes,
        "category": cat,
        "settings": settings,
    }

    last = RepairResult(
        code=ensure_plantuml_bounds(plantuml),
        reason="no strategy applied",
        success_validation=False,
        messages=errors,
        category=cat,
        strategy=order[0],
    )
    for name in order:
        fn = _STRATEGIES.get(name, strategy_spec_rebuild)
        try:
            fixed = fn(plantuml, **kwargs)
        except Exception as exc:
            logger.warning("Strategy %s failed: %s", name, exc)
            continue
        validation = validate_diagram(fixed, diagram_type)
        body = re.sub(r"(?is)@startuml|@enduml", "", fixed or "").strip()
        if len(body) < 8:
            logger.warning("Strategy %s produced an empty diagram; skipping", name)
            continue
        last = RepairResult(
            code=fixed,
            reason=f"{cat} → {name}: {'; '.join(errors[:2]) or 'n/a'}",
            success_validation=validation.ok,
            messages=validation.messages,
            category=cat,
            strategy=name,
        )
        # One strategy per call so the next loop can pick the next unused one.
        return last
    return last
