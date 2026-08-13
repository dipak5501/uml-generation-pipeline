"""Requirement ↔ UML semantic / traceability checks (deterministic)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.plantuml_from_spec import _entity_names, fidelity_report
from app.services.spec_json import extract_named_concepts, extract_nl_relationships
from app.services.uml_structure import (
    declared_class_names,
    declared_component_names,
    declared_object_names,
    declared_package_names,
)

_ALLOW_EXTRA = {
    "abc",
    "object",
    "component",
    "package",
    "interface",
    "enum",
    "note",
    "title",
    "start",
    "stop",
    "driverscript",
}


@dataclass
class SemanticResult:
    ok: bool
    completeness_ok: bool
    correctness_ok: bool
    hallucination_ok: bool
    contradiction_ok: bool
    traceability_ok: bool
    required: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    traces: list[dict[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    recall: float = 0.0


def _declared_names(code: str, diagram_type: str) -> list[str]:
    dtype = (diagram_type or "class").lower()
    if dtype == "object":
        names = declared_object_names(code) + declared_class_names(code)
    elif dtype == "component":
        names = declared_component_names(code) + declared_class_names(code)
    elif dtype == "package":
        names = declared_package_names(code) + declared_class_names(code)
    else:
        names = declared_class_names(code)
    # unique, original order
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


def _stem(name: str) -> str:
    raw = name.lower()
    stripped = re.sub(r"(service|api|store|repository|module|package|item)s?$", "", raw)
    return stripped if len(stripped) >= 5 else raw


def _matches(needle: str, haystack_l: str) -> bool:
    n = needle.lower()
    if re.search(rf"\b{re.escape(n)}\b", haystack_l):
        return True
    stem = _stem(needle)
    return len(stem) >= 4 and stem in haystack_l


def expected_from_requirement(
    requirement: str,
    spec: dict[str, Any] | None = None,
) -> list[str]:
    names: list[str] = []
    if spec:
        names.extend(_entity_names(spec))
    names.extend(extract_named_concepts(requirement or ""))
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        key = n.lower()
        if key in seen or key in _ALLOW_EXTRA:
            continue
        seen.add(key)
        out.append(n)
    return out[:16]


def evaluate_semantics(
    *,
    requirement: str,
    plantuml: str,
    diagram_type: str,
    spec: dict[str, Any] | None = None,
) -> SemanticResult:
    required = expected_from_requirement(requirement, spec)
    code_l = (plantuml or "").lower()
    found: list[str] = []
    missing: list[str] = []
    traces: list[dict[str, str]] = []
    for name in required:
        if _matches(name, code_l):
            found.append(name)
            traces.append({"requirement_concept": name, "uml_evidence": "present", "status": "traced"})
        else:
            missing.append(name)
            traces.append({"requirement_concept": name, "uml_evidence": "", "status": "missing"})

    declared = _declared_names(plantuml, diagram_type)
    extra: list[str] = []
    required_l = {n.lower() for n in required}
    req_stems = {_stem(n) for n in required if len(_stem(n)) >= 4}
    for name in declared:
        key = name.lower()
        if key in _ALLOW_EXTRA or key.startswith("i") and key[1:].lower() in required_l:
            continue
        if key in required_l or _stem(name) in req_stems:
            continue
        if any(_stem(name) and _stem(name) in _stem(r) or _stem(r) in _stem(name) for r in required):
            continue
        extra.append(name)

    recall = len(found) / max(1, len(required)) if required else 1.0
    # Completeness: most required concepts appear
    completeness_ok = recall >= 0.6 and len(missing) <= max(1, len(required) // 3)
    # Hallucination: few extra types vs required
    hallucination_ok = len(extra) <= max(2, len(required) // 2)
    # Correctness: spec fidelity if available, else completeness
    if spec:
        fid = fidelity_report(plantuml, spec, diagram_type)
        correctness_ok = bool(fid.get("ok")) or fid.get("recall", 0) >= 0.6
        if fid.get("generic_placeholders"):
            correctness_ok = False
    else:
        correctness_ok = completeness_ok
    # Contradiction: inheritance/self-deps that invert obvious "is-a" wording
    contradiction_ok = True
    contradiction_msgs: list[str] = []
    for rel in extract_nl_relationships(requirement or ""):
        src, tgt = str(rel.get("source") or ""), str(rel.get("target") or "")
        if not src or not tgt:
            continue
        # If requirement says A inherits B but diagram has B --|> A, flag
        if (rel.get("type") or "") in {"inheritance", "generalization"}:
            pat_wrong = rf"{re.escape(tgt)}\s+--\|>\s+{re.escape(src)}"
            if re.search(pat_wrong, plantuml, re.I):
                contradiction_ok = False
                contradiction_msgs.append(f"Inheritance direction contradicts requirement: {src}/{tgt}")
    if re.search(r"(?m)^\s*(\w+)\s+\.\.>\s+\1\b", plantuml):
        contradiction_ok = False
        contradiction_msgs.append("Self-dependency contradicts a valid architecture")

    traceability_ok = bool(required) and len(found) >= max(1, int(0.5 * len(required)))
    if not required:
        # No extractable concepts: cannot claim traceability failure
        traceability_ok = True
        completeness_ok = True

    msgs: list[str] = []
    if missing:
        msgs.append("Missing required concepts: " + ", ".join(missing[:8]))
    if extra:
        msgs.append("Possible hallucinated types: " + ", ".join(extra[:8]))
    msgs.extend(contradiction_msgs)

    ok = completeness_ok and correctness_ok and hallucination_ok and contradiction_ok and traceability_ok
    return SemanticResult(
        ok=ok,
        completeness_ok=completeness_ok,
        correctness_ok=correctness_ok,
        hallucination_ok=hallucination_ok,
        contradiction_ok=contradiction_ok,
        traceability_ok=traceability_ok,
        required=required,
        found=found,
        missing=missing,
        extra=extra,
        traces=traces,
        messages=msgs,
        recall=recall,
    )
