"""PlantUML syntax validation and package semantic guards."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# PlantUML preprocessor / include directives that must never appear in untrusted diagrams.
_UNSAFE_DIRECTIVE = re.compile(
    r"^\s*!(?:include|includeurl|import|pragma|define|undef|definelong|enddefinelong|"
    r"startsub|endsub|function|endfunction|procedure|endprocedure|return|exit|"
    r"theme|includesub)\b",
    re.I,
)
_SKINPARAM_LINE = re.compile(r"^\s*skinparam\b", re.IGNORECASE)
_STYLE_LINE = re.compile(r"^\s*style\s+\S", re.IGNORECASE)
_INLINE_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_COLOR_WORD_BG = re.compile(
    r"\b(?:BackgroundColor|FontColor|BorderColor|ArrowColor|LineColor|"
    r"Shadowing|RoundCorner|Gradient)\b",
    re.IGNORECASE,
)

_PUBLICATION_SKINPARAMS = (
    "skinparam monochrome true",
    "skinparam shadowing false",
    "skinparam backgroundColor white",
    "skinparam defaultFontColor black",
    "skinparam ArrowColor black",
    "skinparam ClassBorderColor black",
    "skinparam PackageBorderColor black",
    "skinparam ComponentBorderColor black",
    "skinparam ObjectBorderColor black",
    "skinparam NoteBorderColor black",
    "skinparam dpi 150",
)


@dataclass
class ValidationResult:
    ok: bool
    messages: list[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(ok=self.ok and other.ok, messages=self.messages + other.messages)


def strip_plantuml_colors(code: str) -> str:
    """Remove color themes, skinparams, and inline hex fills from PlantUML."""
    if not code or not code.strip():
        return code
    kept: list[str] = []
    in_style_block = False
    for line in code.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if _UNSAFE_DIRECTIVE.match(line):
            continue
        if _SKINPARAM_LINE.match(line) or _STYLE_LINE.match(line):
            continue
        if low.startswith("style ") and "{" in low:
            in_style_block = True
            continue
        if in_style_block:
            if "}" in line:
                in_style_block = False
            continue
        if _COLOR_WORD_BG.search(line):
            continue
        cleaned = _INLINE_HEX.sub("", line)
        cleaned = re.sub(r"\s+#[A-Za-z][\w]*", "", cleaned).rstrip()
        if cleaned.strip():
            kept.append(cleaned)
    return "\n".join(kept).strip()


def apply_publication_plantuml_style(code: str) -> str:
    """Force clean black-and-white publication defaults after @startuml."""
    text = ensure_plantuml_bounds(strip_plantuml_colors(code))
    low = text.lower()
    marker = "@startuml"
    idx = low.find(marker)
    if idx < 0:
        return text
    insert_at = idx + len(marker)
    nl = text.find("\n", insert_at)
    header = "\n".join(_PUBLICATION_SKINPARAMS)
    if nl < 0:
        return f"{text}\n{header}\n"
    return text[: nl + 1] + header + "\n" + text[nl + 1 :]


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


def _infer_type_from_instance(name: str) -> str:
    """user1 → User, cartItem2 → CartItem, Order → Order."""
    base = re.sub(r"\d+$", "", (name or "").strip())
    if not base:
        return "Object"
    if base[0].isupper() and any(c.islower() for c in base[1:]):
        return base
    if "_" in base:
        parts = [p for p in base.split("_") if p]
        return "".join(p[:1].upper() + p[1:] for p in parts) or "Object"
    return base[:1].upper() + base[1:]


def repair_object_declarations(code: str) -> str:
    """Ensure object instances use ``name : Type`` (fixes common LoRA/LLM output)."""
    lines_out: list[str] = []
    for line in code.splitlines():
        raw = line.rstrip()
        # object "foo : Bar" as alias  — already typed in label; leave alone
        if re.match(r'^\s*object\s+"[^"]*"\s+as\s+\w+', raw, flags=re.I):
            lines_out.append(raw)
            continue
        # object alias : Type {?}  — already good
        if re.match(r"^\s*object\s+\w+\s*:\s*\w+", raw, flags=re.I):
            lines_out.append(raw)
            continue
        # object alias {  or object alias
        m = re.match(r"^(\s*)object\s+([A-Za-z_][\w]*)\s*(\{)?\s*$", raw, flags=re.I)
        if m:
            indent, alias, brace = m.groups()
            typ = _infer_type_from_instance(alias)
            suffix = " {" if brace else ""
            lines_out.append(f"{indent}object {alias} : {typ}{suffix}")
            continue
        # object alias with attrs on same line without type
        m = re.match(r"^(\s*)object\s+([A-Za-z_][\w]*)\s+(?![:\"])(.+)$", raw, flags=re.I)
        if m and ":" not in m.group(0).split("object", 1)[1].split("{", 1)[0]:
            indent, alias, rest = m.groups()
            typ = _infer_type_from_instance(alias)
            lines_out.append(f"{indent}object {alias} : {typ} {rest}".rstrip())
            continue
        lines_out.append(raw)
    return "\n".join(lines_out)


def repair_package_nesting(code: str) -> str:
    """Rewrite peer ``package a.b.c {`` blocks into one nested package tree.

    Leaves non-dotted packages untouched when there are fewer than two dotted
    peers. Deterministic post-process for the common LoRA failure of flat
    dotted package peers (which also breaks line-dedupe if emitted naively).
    """
    text = ensure_plantuml_bounds(code)
    dotted = re.findall(r"(?im)^\s*package\s+([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+)\s*\{", text)
    if len(dotted) < 2:
        return text

    pattern = re.compile(
        r"(?im)^(?P<indent>\s*)package\s+(?P<name>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+)\s*\{(?P<body>.*?)^(?P=indent)\}",
        re.S,
    )
    packages: list[tuple[str, str]] = []
    for m in pattern.finditer(text):
        packages.append((m.group("name"), m.group("body")))
    if len(packages) < 2:
        return text

    # Nested dict: part → {__kids__, __body__}
    root: dict = {"__kids__": {}, "__body__": []}
    for name, body in packages:
        node = root
        for part in name.split("."):
            kids = node.setdefault("__kids__", {})
            node = kids.setdefault(part, {"__kids__": {}, "__body__": []})
        cleaned = [ln.rstrip() for ln in body.strip("\n").splitlines() if ln.strip()]
        node.setdefault("__body__", []).extend(cleaned)

    def _emit(node: dict, indent: str = "") -> list[str]:
        out: list[str] = []
        for part, child in node.get("__kids__", {}).items():
            out.append(f"{indent}package {part} {{")
            for ln in child.get("__body__", []):
                out.append(f"{indent}  {ln.lstrip()}")
            out.extend(_emit(child, indent + "  "))
            out.append(f"{indent}}}")
        return out

    tree_block = "\n".join(_emit(root))
    titles = re.findall(r"(?im)^\s*title\b.*$", text)
    deps_raw = [
        ln
        for ln in text.splitlines()
        if re.search(r"(\.\.>|->|-->)", ln)
    ]
    fixed_deps: list[str] = []
    for ln in deps_raw:
        fixed = ln
        for full, _body in packages:
            leaf = full.split(".")[-1]
            fixed = re.sub(rf"\b{re.escape(full)}\b", leaf, fixed)
        if re.search(r"^\s*([A-Za-z_][\w.]*)\s+(\.\.>|->|-->)\s*\1\b", fixed):
            continue
        fixed_deps.append(fixed)

    parts = ["@startuml", *titles, tree_block, *fixed_deps, "@enduml"]
    return "\n".join(p for p in parts if str(p).strip()) + "\n"

def repair_component_interfaces(code: str) -> str:
    """Drop auto-invented ``() \"IName\" as IName`` stubs that mirror component names."""
    comps = {
        re.sub(r"[^\w]", "", m.group(1).split()[0]).lower()
        for m in re.finditer(r"(?im)^\s*\[([^\]]+)\]", code)
        if m.group(1).strip()
    }
    comps |= {
        m.group(1).lower()
        for m in re.finditer(r"(?im)^\s*component\s+([A-Za-z_][\w]*)", code)
    }
    drop_aliases: set[str] = set()
    lines_out: list[str] = []
    for line in code.splitlines():
        m = re.match(r'^\s*\(\)\s*"([^"]+)"\s+as\s+([A-Za-z_][\w]*)\s*$', line)
        if m:
            label, alias = m.group(1).strip(), m.group(2)
            stem = re.sub(r"^I", "", label, flags=re.I)
            stem = re.sub(r"(Service|Api|Store)$", "", stem, flags=re.I)
            if label.lower().startswith("i") and any(
                stem.lower() == c or c.startswith(stem.lower()) or stem.lower() in c
                for c in comps
            ):
                drop_aliases.add(alias.lower())
                continue
        lines_out.append(line)
    if not drop_aliases:
        return code
    cleaned: list[str] = []
    for line in lines_out:
        if re.search(r"(-->|\.\.>|->)", line):
            toks = re.findall(r"[A-Za-z_][\w]*", line)
            if toks and toks[-1].lower() in drop_aliases:
                continue
        cleaned.append(line)
    return "\n".join(cleaned)


def sanitize_plantuml_output(
    code: str,
    *,
    max_lines: int = 180,
    diagram_type: str | None = None,
) -> str:
    """Clean common LLM failures: duplicate tags, repeated lines, runaway output."""
    text = ensure_plantuml_bounds(code)
    # Drop accidental @startchen / ER leftovers that break UML renders
    text = re.sub(r"(?im)^@startchen\b.*$", "", text)
    text = re.sub(r"(?im)^@endchen\b.*$", "", text)
    text = normalize_plantuml_relations(text)
    text = strip_unsafe_plantuml_directives(text)

    dtype = (diagram_type or "").lower().strip()
    if dtype == "object" or (not dtype and re.search(r"(?im)^\s*object\s+", text)):
        text = repair_object_declarations(text)
    if dtype == "package" or (
        not dtype and len(re.findall(r"(?im)^\s*package\s+\S+\.\S+", text)) >= 2
    ):
        text = repair_package_nesting(text)
    if dtype == "component" or (not dtype and re.search(r"(?im)^\s*\[", text)):
        text = repair_component_interfaces(text)

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
    return apply_publication_plantuml_style(body.strip() + "\n")


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
    # Accept either `object name : Type` or `object "name : Type" as alias`
    typed = bool(re.search(r"(?im)^\s*object\s+\w+\s*:\s*\w+", code))
    labeled = bool(re.search(r'(?im)^\s*object\s+"[^"]+\s*:\s*[^"]+"\s+as\s+\w+', code))
    any_object = bool(re.search(r"(?im)^\s*object\s+", code))
    if any_object and not typed and not labeled:
        msgs.append("Object instances should use name:Type syntax (e.g. object cart1 : Cart)")
    # Flag bare `object Name {` even if another object is typed
    for m in re.finditer(r"(?im)^\s*object\s+(\w+)\s*\{", code):
        # Look back on same match — if line has no colon before brace
        line = m.group(0)
        if ":" not in line:
            msgs.append(f"Object '{m.group(1)}' is missing :Type before attribute block")
            break
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
