"""PlantUML syntax validation and package semantic guards."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    messages: list[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(ok=self.ok and other.ok, messages=self.messages + other.messages)


def ensure_plantuml_bounds(code: str) -> str:
    text = code.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:plantuml)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    if "@startuml" not in text.lower():
        text = f"@startuml\n{text}\n@enduml"
    elif "@enduml" not in text.lower():
        text = text + "\n@enduml"
    # Keep only first diagram block
    m = re.search(r"@startuml.*?@enduml", text, flags=re.I | re.S)
    return m.group(0) if m else text


def validate_basic_syntax(code: str) -> ValidationResult:
    msgs: list[str] = []
    if "@startuml" not in code.lower():
        msgs.append("Missing @startuml")
    if "@enduml" not in code.lower():
        msgs.append("Missing @enduml")
    if code.lower().count("@startuml") > 1:
        msgs.append("Multiple @startuml blocks")
    # Unbalanced braces
    if code.count("{") != code.count("}"):
        msgs.append("Unbalanced curly braces")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_package_semantics(code: str) -> ValidationResult:
    """Guards for the hardest failure mode: package diagrams."""
    msgs: list[str] = []
    lines = code.splitlines()

    # Self-referential dependencies
    for line in lines:
        m = re.search(r"^\s*([A-Za-z_][\w.]*)\s+(\.\.>|->|-->)\s*\1\b", line)
        if m:
            msgs.append(f"Self-referential dependency: {line.strip()}")

    # Dotted names used as peer packages without nesting
    # Flag patterns like: package com.app.core (suggests nesting confusion)
    dotted_pkgs = re.findall(r"package\s+([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+)", code)
    if len(dotted_pkgs) >= 2:
        # If many dotted peer packages and no nested package { blocks, warn
        nested = bool(re.search(r"package\s+\w+\s*\{", code))
        if not nested:
            msgs.append(
                "Multiple dotted package names without nesting; "
                "prefer nested package { } for containment"
            )

    # Contained packages declared again as top-level peers (simple heuristic)
    top_level = re.findall(r"(?m)^package\s+(\w+)", code)
    if len(top_level) != len(set(top_level)):
        msgs.append("Duplicate package names at declaration sites")

    # Confusion: using +-- containment connector incorrectly between same package
    for line in lines:
        if re.search(r"^\s*(\w+)\s+\+--\s*\1\b", line):
            msgs.append(f"Invalid self-containment: {line.strip()}")

    return ValidationResult(ok=not msgs, messages=msgs)


def validate_object_syntax(code: str) -> ValidationResult:
    msgs: list[str] = []
    # Common failure: object Name without :Type and with invalid attribute block
    if "object " in code.lower() and not re.search(r"object\s+\w+\s*:\s*\w+", code, re.I):
        if re.search(r"object\s+\w+\s*\{", code, re.I):
            msgs.append("Object instances should use name:Type syntax")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_component_syntax(code: str) -> ValidationResult:
    msgs: list[str] = []
    # Broken interface: () without name
    if re.search(r"\(\)\s*$", code, re.M):
        msgs.append("Empty component interface notation")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_diagram(code: str, diagram_type: str) -> ValidationResult:
    code = ensure_plantuml_bounds(code)
    result = validate_basic_syntax(code)
    if diagram_type == "package":
        result = result.merge(validate_package_semantics(code))
    elif diagram_type == "object":
        result = result.merge(validate_object_syntax(code))
    elif diagram_type == "component":
        result = result.merge(validate_component_syntax(code))
    return result
