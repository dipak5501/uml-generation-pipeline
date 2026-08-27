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
    variables: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    @property
    def has_type_declarations(self) -> bool:
        """True only when real class/interface/enum declarations exist."""
        return bool(self.classes)

    def entity_names(self, n: int = 6) -> list[str]:
        """Return declared type names only — never promote variables to classes."""
        out: list[str] = []
        for name in self.classes:
            if not name or re.match(r"^Module\d+$", name, re.I):
                continue
            if name not in out:
                out.append(name)
            if len(out) >= n:
                break
        return out

    def script_process_steps(self, source: str = "") -> list[str]:
        """Human-readable steps for scripts that define no classes."""
        blob = (source or "").lower()
        steps = [s for s in self.steps if s and len(s) > 2][:10]
        # Always inject structural script stages when detectable (more reliable than prints alone)
        preamble: list[str] = []
        if self.imports or "import " in blob:
            preamble.append("Import dependencies")
        if self.variables:
            preamble.append("Configure paths / parameters")
        if "py2puml" in blob:
            preamble.append("Analyze package with py2puml")
            preamble.append("Emit PlantUML lines")
        if "open(" in blob and ("write" in blob or "f.write" in blob or ".puml" in blob):
            preamble.append("Write .puml output file")
        if any("success" in s.lower() for s in steps) or "success" in blob:
            preamble.append("Report success")
        elif preamble:
            preamble.append("Finish")
        merged = preamble + [s for s in steps if s not in preamble]
        if not merged:
            merged = ["Initialize", "Run script logic", "Finish"]
        out: list[str] = []
        for s in merged:
            if s not in out:
                out.append(s)
        return out[:10]


def detect_language(code: str) -> str:
    # C/C++ before JavaScript — ``const`` in C otherwise matches JS heuristics.
    if re.search(r"^\s*#\s*include\s*[<\"]", code, re.M) or re.search(
        r"\btypedef\s+struct\b", code
    ):
        if re.search(r"\bstd::|namespace\s+\w+|class\s+\w+\s*:\s*public", code):
            return "cpp"
        return "c"
    # Java before Python — both use ``class``, but Java uses braces / JVM types.
    if re.search(r"\b(public|private|protected)\s+(class|interface|enum)\s+\w+", code):
        return "java"
    if re.search(r"^\s*import\s+[\w.*]+\s*;\s*$|^\s*package\s+[\w.]+\s*;\s*$", code, re.M):
        return "java"
    if re.search(r"^\s*(public\s+)?class\s+\w+\s*\{", code, re.M) and re.search(
        r"\b(boolean|void|String|int|double|float|long)\b", code
    ):
        return "java"
    # Python: ``def`` or ``class Name:`` (colon syntax, not brace body).
    if re.search(r"^\s*def\s+\w+", code, re.M):
        return "python"
    if re.search(r"^\s*class\s+\w+[^:{]*:", code, re.M):
        return "python"
    python_script = [
        r"^\s*#",
        r"\bprint\s*\(",
        r"\binput\s*\(",
        r"\belif\b",
        r"\b(True|False|None)\b",
        r"\bimport\s+\w",
        r"\bfrom\s+\w+\s+import",
        r"\bint\s*\(",
        r"\bfloat\s*\(",
        r"\bstr\s*\(",
    ]
    if sum(1 for p in python_script if re.search(p, code, re.M)) >= 2:
        return "python"
    if re.search(r"\b(function|const|let|var|export\s+class|interface)\b", code) and ":" in code and "=>" in code:
        return "typescript"
    if re.search(r"\b(function|const|let|var|export\s+class|interface)\b", code):
        return "javascript"
    if "fn " in code and ("impl " in code or "struct " in code):
        return "rust"
    if re.search(r"^\s*package\s+\w+|func\s+\(\w+\s+\*", code, re.M) or (
        "func " in code and "struct {" in code.replace(" ", "")
    ):
        if "func " in code and "package " in code:
            return "go"
    if "namespace " in code and re.search(r"\bpublic\s+class\b", code):
        return "csharp"
    if re.search(r"\b(fun |open class |val |var )\b", code) and "class " in code:
        return "kotlin"
    if re.search(r"\b(func |var |let |class )\b", code) and "->" in code:
        return "swift"
    if re.search(r"\bclass\s+\w+\s*(:|\{)|#include\b", code) and ("public:" in code or "std::" in code or "};" in code):
        if "public:" in code or re.search(r"class\s+\w+\s*:\s*public", code):
            return "cpp"
    if re.search(r"\b(attr_accessor|def\s+\w+|end\b)", code) and "class " in code:
        return "ruby"
    if "<?php" in code or re.search(r"\bfunction\s+\w+\s*\(.*\)\s*\{", code) and "class " in code:
        if "<?php" in code or "$" in code:
            return "php"
    if re.search(r"\b(def |extends |val )\b", code) and "class " in code and ":" in code:
        return "scala"
    if "class " in code and "=>" in code and ";" in code:
        return "dart"
    if "defmodule " in code or "do:" in code:
        return "elixir"
    if re.search(r"\bdata\s+\w+\s*=", code) or "::" in code and "->" in code:
        return "haskell"
    if "setRefClass" in code or "<-" in code and "function(" in code:
        return "r"
    if "classdef " in code:
        return "matlab"
    if "package " in code and "bless" in code:
        return "perl"
    if "function " in code and "end" in code and "setmetatable" in code:
        return "lua"
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
        r"\b(class|def|function|interface|struct|enum|public|private|package|import|typedef)\b",
        r"[{};]\s*$",
        r"^\s{2,}\w+",
        r"->|=>|::",
        r"\(\s*self\s*[,)]",
        r"\bprint\s*\(",
        r"\binput\s*\(",
        r"^\s*#",
        r"^\s*#\s*include\b",
    ]
    for p in patterns:
        if re.search(p, t, re.M):
            signals += 1
    return signals >= 2


def analyze_source_code(code: str) -> CodeStructure:
    lang = detect_language(code)
    struct = CodeStructure(language=lang)

    struct.imports = re.findall(r"(?m)^\s*(?:import|from|using|require)\s+[^\n]+", code)[:20]
    struct.variables = [
        v
        for v in re.findall(r"(?m)^\s*([A-Za-z_]\w*)\s*=", code)
        if v not in {"if", "elif", "for", "while"}
    ][:12]
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            step = stripped.lstrip("#").strip()
            if step:
                struct.steps.append(step)
        m = re.search(r'print\s*\(\s*f?["\']([^"\']+)["\']', stripped)
        if m:
            step = m.group(1).rstrip(":").strip()
            # Drop f-string braces noise: Analyzing {domain_module}...
            step = re.sub(r"\{[^}]*\}", "<value>", step).strip()
            if step:
                struct.steps.append(step)

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
            method_txt = ", ".join(methods[:8]) if methods else "(no methods extracted)"
            lines.append(f"- {c}: {method_txt}")
            if c in s.bases:
                lines.append(f"  - inherits: {', '.join(s.bases[c])}")
    else:
        lines.append("- (none — source is a script/driver with no class/interface declarations)")
        lines.append("  Do NOT invent classes from variable names or string literals.")
    lines.append("### Relationships")
    if s.bases:
        for child, parents in s.bases.items():
            for p in parents:
                lines.append(f"- {child} inherits {p}")
    elif len(s.classes) >= 2:
        lines.append(f"- {s.classes[0]} associates with {s.classes[1]}")
    elif not s.classes:
        lines.append("- (none — no types to relate)")
    else:
        lines.append("- (single type; no inter-type relationships extracted)")
    # Always expose process steps for scripts; required for flowchart recovery
    if diagram_type == "flowchart" or not s.classes:
        lines.append("### Process steps")
        steps = s.script_process_steps() or ["Initialize", "Process", "Finalize"]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
    if s.imports:
        lines.append("### Imports / dependencies")
        for imp in s.imports[:8]:
            lines.append(f"- {imp.strip()}")
    if s.variables and not s.classes:
        lines.append("### Script configuration (not UML classes)")
        for var in s.variables[:8]:
            lines.append(f"- {var}: configuration / local binding")
    if s.classes:
        lines.append("### Modules")
        lines.append("- domain: primary types from source")
    return "\n".join(lines)
