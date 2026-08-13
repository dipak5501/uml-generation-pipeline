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


_REL_WORD_MAP = {
    "inheritance": "--|>",
    "inherits": "--|>",
    "extends": "--|>",
    "generalization": "--|>",
    "association": "-->",
    "associates": "-->",
    "link": "-->",
    "composition": "*--",
    "composes": "*--",
    "aggregation": "o--",
    "aggregates": "o--",
    "dependency": "..>",
    "depends": "..>",
    "uses": "..>",
    "realization": "..|>",
    "realizes": "..|>",
    "containment": "+--",
    "contains": "+--",
}


def normalize_plantuml_relations(code: str) -> str:
    """Rewrite invalid LoRA/LLM connectors like ``A --inheritance--> B;`` into PlantUML."""

    def _rewrite_line(line: str) -> str:
        raw = line.rstrip()
        # class Foo;  → class Foo
        m = re.match(r"^(\s*(?:class|interface|enum|abstract\s+class)\s+\S+)\s*;\s*$", raw, flags=re.I)
        if m:
            return m.group(1)
        # A --word--> B;  or A -- word --> B
        m = re.match(
            r"^(\s*)([A-Za-z_][\w.]*)\s+--\s*([A-Za-z_]+)\s*-->\s*([A-Za-z_][\w.]*)\s*;?\s*$",
            raw,
        )
        if m:
            indent, src, word, tgt = m.groups()
            arrow = _REL_WORD_MAP.get(word.lower(), "-->")
            return f"{indent}{src} {arrow} {tgt}"
        # A --|> B; trailing semicolon on normal arrows
        m = re.match(
            r"^(\s*)([A-Za-z_][\w.]*)\s+"
            r"((?:<\|\-\-|\-\-\|>|\*\-\-|o\-\-|\.\.\|>|\.\.>|\-\->|\+\-\-))\s*"
            r"([A-Za-z_][\w.]*)\s*;\s*$",
            raw,
        )
        if m:
            indent, src, arrow, tgt = m.groups()
            return f"{indent}{src} {arrow} {tgt}"
        # Attribute / method lines inside class blocks ending with ;
        # Do NOT strip activity-diagram steps (`:Step;`) or control lines.
        stripped = raw.rstrip()
        lead = stripped.lstrip()
        if lead.startswith((":", "if ", "else", "endif", "stop", "start", "fork", "again")):
            return raw
        if stripped.endswith(";") and "--" not in stripped and ".." not in stripped and not lead.startswith("@"):
            if re.search(r"^\s*[+\-#~]?[\w].*[:\(]", stripped):
                return stripped[:-1].rstrip()
        return raw

    return "\n".join(_rewrite_line(ln) for ln in code.splitlines())


# PlantUML preprocessor / include directives that must never appear in untrusted diagrams.
_UNSAFE_DIRECTIVE = re.compile(
    r"^\s*!(?:include|includeurl|import|pragma|define|undef|definelong|enddefinelong|"
    r"startsub|endsub|function|endfunction|procedure|endprocedure|return|exit|"
    r"theme|includesub)\b",
    re.I,
)


def strip_unsafe_plantuml_directives(code: str) -> str:
    """Drop preprocessor / include lines that enable local file read or SSRF."""
    kept: list[str] = []
    for line in code.splitlines():
        if _UNSAFE_DIRECTIVE.match(line):
            continue
        if re.search(r"(?i)!(?:include|includeurl|import)\b", line):
            line = re.sub(r"(?i)!(?:include|includeurl|import)\b[^\n]*", "", line)
        kept.append(line)
    return "\n".join(kept)


def sanitize_plantuml_output(code: str, *, max_lines: int = 120) -> str:
    """Clean common LLM failures: duplicate tags, repeated lines, runaway output."""
    text = ensure_plantuml_bounds(code)
    text = normalize_plantuml_relations(text)
    text = strip_unsafe_plantuml_directives(text)
    lines = text.splitlines()
    cleaned: list[str] = []
    seen: set[str] = set()
    start_count = 0
    for line in lines:
        low = line.strip().lower()
        if low.startswith("@startuml"):
            start_count += 1
            if start_count > 1:
                continue
        if low.startswith("@enduml") and start_count == 0:
            continue
        key = line.strip()
        if key and key in seen and not key.startswith("@") and not key.endswith("}"):
            continue
        if key:
            seen.add(key)
        cleaned.append(line.rstrip())
        if len(cleaned) >= max_lines and not low.startswith("@enduml"):
            cleaned.append("@enduml")
            break
    if not cleaned or cleaned[-1].strip().lower() != "@enduml":
        if cleaned and cleaned[-1].strip().lower().startswith("@enduml"):
            pass
        else:
            cleaned.append("@enduml")
    # Balance braces inside diagram body
    body = "\n".join(cleaned)
    opens = body.count("{")
    closes = body.count("}")
    if opens > closes:
        body = body.replace("@enduml", "}" * (opens - closes) + "\n@enduml", 1)
    return body.strip() + "\n"


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
    # Empty @startuml/@enduml still "renders" as a blank PNG — treat as invalid
    body = re.sub(r"(?im)@startuml|@enduml|^\s*title\b[^\n]*$|^\s*skinparam\b[^\n]*$", "", code)
    body = re.sub(r"(?m)^\s*(left to right direction|hide\b.*|!theme\b.*)$", "", body)
    if len(body.strip()) < 8:
        msgs.append("Diagram body is empty or incomplete")
    # Worded arrows are not PlantUML (e.g. A --inheritance--> B)
    if re.search(r"--\s*[A-Za-z_]{3,}\s*-->", code):
        msgs.append("Invalid worded relationship arrow (use --|>, -->, *--, o--, ..>)")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_package_semantics(code: str) -> ValidationResult:
    """Guards for the hardest failure mode: package diagrams."""
    msgs: list[str] = []
    lines = code.splitlines()
    body = re.sub(r"(?im)@startuml|@enduml|^\s*title\b[^\n]*$", "", code).strip()
    if len(body) < 12:
        msgs.append("Package diagram appears empty or incomplete")

    if not re.search(r"(?im)^\s*package\s+", code):
        msgs.append("Package diagram has no package { } declarations")
    # Reject bare "package Name;" / "package Name" without a block body
    if not re.search(r"(?im)^\s*package\s+\S[^\n{]*\{", code):
        msgs.append("Package diagram needs package Name { ... } blocks, not bare package lines")
    # Require some containment or dependency content inside packages
    if re.search(r"(?im)^\s*package\s+\S[^\n{]*\{", code):
        inner = re.sub(r"(?is)@startuml|@enduml", "", code)
        has_inner_type = bool(
            re.search(r"(?im)^\s*(class|interface|component|package)\s+\w+", inner)
        )
        has_dep = bool(re.search(r"\.\.>|->|-->|\+--", inner))
        if not has_inner_type and not has_dep:
            msgs.append("Package blocks are empty (no nested types or dependencies)")

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


def validate_flowchart_syntax(code: str) -> ValidationResult:
    msgs: list[str] = []
    # Strip diagram delimiters so "@startuml" does not count as activity "start"
    body = re.sub(r"(?is)@startuml|@enduml", "", code)
    low = body.lower()
    has_step = bool(re.search(r"(?m)^\s*:[^;\n]+;", body))
    has_flow_start = bool(re.search(r"(?m)^\s*start\s*$", body, re.I))
    has_flow_stop = bool(re.search(r"(?m)^\s*(stop|end)\s*$", body, re.I))
    has_activity = has_flow_start or has_step or has_flow_stop or "endif" in low
    has_class_like = bool(re.search(r"(?m)^\s*class\s+\w+", body))
    has_object_like = bool(re.search(r"(?m)^\s*object\s+\w+", body))

    if (has_class_like or has_object_like) and not has_activity:
        msgs.append(
            "Flowchart looks like a structural UML diagram; "
            "use activity syntax (start / :Step; / if / stop)"
        )
    if not has_step and not has_flow_start:
        msgs.append("Flowchart has no activity steps (:Step;) or start")
    if has_flow_start and not has_flow_stop:
        msgs.append("Flowchart has start but missing stop/end")
    # Class-style arrows inside activity diagrams are usually wrong
    if has_activity and re.search(r"(?m)^\s*:\w+.*-->\s*\w+", body):
        msgs.append("Flowchart steps should not use class-style --> arrows")
    return ValidationResult(ok=not msgs, messages=msgs)


def validate_diagram(code: str, diagram_type: str) -> ValidationResult:
    from app.services.uml_structure import validate_uml_structure

    code = ensure_plantuml_bounds(code)
    result = validate_basic_syntax(code)
    if diagram_type == "package":
        result = result.merge(validate_package_semantics(code))
    elif diagram_type == "object":
        result = result.merge(validate_object_syntax(code))
    elif diagram_type == "component":
        result = result.merge(validate_component_syntax(code))
    elif diagram_type == "flowchart":
        result = result.merge(validate_flowchart_syntax(code))
    # Type-specific UML structure (class members, components, packages, …)
    if diagram_type in {"class", "object", "component", "package", "sequence"}:
        result = result.merge(validate_uml_structure(code, diagram_type))
    return result
