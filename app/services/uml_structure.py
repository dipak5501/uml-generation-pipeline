"""Diagram-specific UML structural rules (beyond raw PlantUML syntax)."""

from __future__ import annotations

import re

from app.services.plantuml_validate import ValidationResult, ensure_plantuml_bounds

_CLASS_DECL = re.compile(
    r"(?im)^\s*(?:abstract\s+)?(?:class|interface|enum|annotation)\s+([A-Za-z_][\w.]*)"
)
_OBJECT_DECL = re.compile(r"(?im)^\s*object\s+(?:\"[^\"]+\"\s+as\s+)?([A-Za-z_][\w]*)")
_COMPONENT_DECL = re.compile(
    r"(?im)^\s*(?:\[([^\]]+)\]|(?:component|node|folder|frame|cloud|database)\s+([A-Za-z_][\w.]*))"
)
_PACKAGE_DECL = re.compile(r"(?im)^\s*package\s+(?:\"([^\"]+)\"|([A-Za-z_][\w.]*))")


def _body(code: str) -> str:
    text = ensure_plantuml_bounds(code)
    return re.sub(r"(?is)@startuml|@enduml", "", text)


def declared_class_names(code: str) -> list[str]:
    return [m.group(1) for m in _CLASS_DECL.finditer(_body(code))]


def declared_object_names(code: str) -> list[str]:
    return [m.group(1) for m in _OBJECT_DECL.finditer(_body(code))]


def declared_component_names(code: str) -> list[str]:
    names: list[str] = []
    for m in _COMPONENT_DECL.finditer(_body(code)):
        raw = (m.group(1) or m.group(2) or "").strip()
        raw = re.sub(r"\s+as\s+\S+$", "", raw, flags=re.I)
        raw = raw.strip(" \"'")
        if raw:
            names.append(re.sub(r"[^\w.]", "_", raw.split()[0]))
    return names


def declared_package_names(code: str) -> list[str]:
    names: list[str] = []
    for m in _PACKAGE_DECL.finditer(_body(code)):
        names.append((m.group(1) or m.group(2) or "").strip())
    return [n for n in names if n]


def validate_class_structure(code: str) -> ValidationResult:
    msgs: list[str] = []
    body = _body(code)
    classes = declared_class_names(code)
    if not classes:
        msgs.append("Class diagram has no class/interface/enum declarations")
    if len(classes) != len({c.lower() for c in classes}):
        msgs.append("Duplicate class declarations")
    # Unsupported / worded relationships after normalize should already be gone
    if re.search(r"--\s*[A-Za-z]+\s*-->", body):
        msgs.append("Unsupported worded relationship arrow")
    # Member syntax inside class blocks: allow empty classes
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_object_structure(code: str) -> ValidationResult:
    msgs: list[str] = []
    objects = declared_object_names(code)
    if not objects:
        msgs.append("Object diagram has no object instances")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_component_structure(code: str) -> ValidationResult:
    msgs: list[str] = []
    comps = declared_component_names(code)
    if not comps:
        msgs.append("Component diagram has no components")
    if len(comps) != len({c.lower() for c in comps}):
        msgs.append("Duplicate component names")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_package_structure(code: str) -> ValidationResult:
    msgs: list[str] = []
    pkgs = declared_package_names(code)
    if not pkgs:
        msgs.append("Package diagram has no package declarations")
    if not re.search(r"package\s+.+\s*\{", _body(code), re.I):
        msgs.append("Package diagram needs nested package { } blocks")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_uml_structure(code: str, diagram_type: str) -> ValidationResult:
    dtype = (diagram_type or "class").lower()
    if dtype == "class":
        return validate_class_structure(code)
    if dtype == "object":
        return validate_object_structure(code)
    if dtype == "component":
        return validate_component_structure(code)
    if dtype == "package":
        return validate_package_structure(code)
    if dtype == "sequence":
        return ValidationResult(
            ok=False,
            messages=["Sequence diagrams are not a supported generation type in this pipeline"],
        )
    return ValidationResult(ok=True, messages=[])
