"""Lightweight multi-language structure extraction from source code."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CodeStructure:
    language: str = "unknown"
    classes: list[str] = field(default_factory=list)
    bases: dict[str, list[str]] = field(default_factory=dict)
    methods: dict[str, list[str]] = field(default_factory=dict)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    def entity_names(self, n: int = 6) -> list[str]:
        names = list(self.classes) + [f for f in self.functions if f[:1].isupper()]
        if not names:
            names = list(self.functions)
        # Unique preserve order
        out: list[str] = []
        for name in names:
            if name not in out:
                out.append(name)
            if len(out) >= n:
                break
        while len(out) < n:
            out.append(f"Module{len(out)+1}")
        return out


def detect_language(code: str) -> str:
    if re.search(r"^\s*def\s+\w+|^\s*class\s+\w+", code, re.M):
        return "python"
    if re.search(r"\b(function|const|let|var|export\s+class|interface)\b", code):
        return "javascript"
    if re.search(r"\b(public|private|protected)\s+(class|interface|enum)\s+\w+", code):
        return "java"
    if re.search(r"(?m)^\s*import\s+[\w.*]+\s*;\s*$|(?m)^\s*package\s+[\w.]+\s*;\s*$", code):
        return "java"
    if "fn " in code and "impl " in code:
        return "rust"
    return "unknown"


def resolve_input_mode(requirement: str, input_mode: str = "requirement") -> str:
    """Normalize requirement vs source_code based on content heuristics."""
    if input_mode == "requirement" and looks_like_source_code(requirement):
        return "source_code"
    return input_mode


def detect_source_language(requirement: str, input_mode: str = "requirement") -> str | None:
    """Return detected language for source-code inputs, else None."""
    mode = resolve_input_mode(requirement, input_mode)
    if mode != "source_code":
        return None
    return detect_language(requirement)


def looks_like_source_code(text: str) -> bool:
    t = text.strip()
    if len(t) < 8:
        return False
    signals = 0
    patterns = [
        r"\b(class|def|function|interface|struct|enum|public|private|package|import)\b",
        r"[{};]\s*$",
        r"^\s{2,}\w+",
        r"->|=>|::",
        r"\(\s*self\s*[,)]",
    ]
    for p in patterns:
        if re.search(p, t, re.M):
            signals += 1
    return signals >= 2


def analyze_source_code(code: str) -> CodeStructure:
    lang = detect_language(code)
    struct = CodeStructure(language=lang)

    struct.imports = re.findall(r"(?m)^\s*(?:import|from|using|require)\s+[^\n]+", code)[:20]

    if lang == "python":
        for m in re.finditer(r"(?m)^\s*class\s+(\w+)(?:\s*\(([^)]*)\))?:", code):
            name = m.group(1)
            bases = [b.strip() for b in (m.group(2) or "").split(",") if b.strip() and b.strip() != "object"]
            struct.classes.append(name)
            if bases:
                struct.bases[name] = bases
        for m in re.finditer(r"(?m)^\s*def\s+(\w+)\s*\(", code):
            struct.functions.append(m.group(1))
        # Methods under class (approx by indentation blocks ignored — collect all defs after class)
        current = None
        for line in code.splitlines():
            cm = re.match(r"^class\s+(\w+)", line)
            if cm:
                current = cm.group(1)
                struct.methods.setdefault(current, [])
                continue
            if current and re.match(r"^\s{4}def\s+(\w+)", line):
                struct.methods[current].append(re.match(r"^\s{4}def\s+(\w+)", line).group(1))
            elif line and not line.startswith((" ", "\t")) and not line.startswith("#"):
                if not line.startswith("@"):
                    current = None
    else:
        for m in re.finditer(r"\b(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?", code):
            name = m.group(1)
            struct.classes.append(name)
            bases = []
            if m.group(2):
                bases.append(m.group(2))
            if m.group(3):
                bases.extend([x.strip() for x in m.group(3).split(",") if x.strip()])
            if bases:
                struct.bases[name] = bases
        for m in re.finditer(r"\b(?:function|func|fn)\s+(\w+)\s*\(", code):
            struct.functions.append(m.group(1))
        for m in re.finditer(r"\b(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\([^;]*\)\s*\{", code):
            name = m.group(1)
            if name not in {"if", "for", "while", "switch", "catch"} and name not in struct.functions:
                struct.functions.append(name)

    # de-dupe
    struct.classes = list(dict.fromkeys(struct.classes))
    struct.functions = list(dict.fromkeys(struct.functions))
    return struct


def structure_to_spec(code: str, diagram_type: str) -> str:
    s = analyze_source_code(code)
    lines = [
        "## Technical Specification (from source code)",
        f"### Detected language\n- {s.language}",
        "### Source intent\nReverse-engineered structural model from provided source code.",
        "### Entities",
    ]
    if s.classes:
        for c in s.classes:
            methods = s.methods.get(c) or []
            method_txt = ", ".join(methods[:8]) if methods else "id, name"
            lines.append(f"- {c}: {method_txt}")
            if c in s.bases:
                lines.append(f"  - inherits: {', '.join(s.bases[c])}")
    else:
        for f in s.functions[:8]:
            lines.append(f"- {f}: callable unit")
    lines.append("### Relationships")
    if s.bases:
        for child, parents in s.bases.items():
            for p in parents:
                lines.append(f"- {child} inherits {p}")
    elif len(s.classes) >= 2:
        lines.append(f"- {s.classes[0]} associates with {s.classes[1]}")
    else:
        lines.append("- modules collaborate through call dependencies")
    if diagram_type == "flowchart":
        lines.append("### Process steps")
        steps = s.functions[:6] or s.classes[:6] or ["Initialize", "Process", "Finalize"]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
    if s.imports:
        lines.append("### Imports / dependencies")
        for imp in s.imports[:8]:
            lines.append(f"- {imp.strip()}")
    lines.append("### Modules")
    lines.append("- domain: primary types from source")
    lines.append("- application: orchestration / services")
    return "\n".join(lines)
