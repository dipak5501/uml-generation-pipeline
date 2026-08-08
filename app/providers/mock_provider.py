"""Mock provider for offline runs — content-aware diagrams."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_STOP = {
    "you", "are", "the", "and", "for", "with", "from", "that", "this", "your",
    "into", "only", "valid", "plantuml", "expert", "convert", "technical",
    "specification", "diagram", "class", "object", "component", "package",
    "include", "classes", "attributes", "methods", "correct", "relationship",
    "notation", "output", "between", "startuml", "enduml", "markdown", "fences",
    "commentary", "outside", "keep", "readable", "avoid", "unnecessary",
    "complexity", "private", "reasoning", "final", "rules", "generate",
    "uml", "software", "requirement", "feature", "story", "act",
    "senior", "system", "systems", "architect", "produce", "detailed", "suitable",
    "design", "phase", "engineering", "identify", "structure", "entities",
    "when", "relevant", "modules", "interfaces", "packages", "hierarchy",
    "relationships", "association", "composition", "aggregation", "dependency",
    "ownership", "containment", "inheritance", "appropriate", "constraints",
    "code", "source", "chain", "thought", "clear", "structured", "headings",
    "bullets", "target", "type", "will", "would", "want", "need", "needs", "should",
    "shall", "must", "may", "might", "can", "have", "has", "been", "being",
    "their", "them", "they",
    "also", "using", "used", "uses", "via", "per", "each", "all", "any",
    "some", "more", "than", "into", "onto", "about", "above", "after",
    "before", "below", "between", "under", "over", "where", "which", "who",
    "whom", "whose", "what", "how", "why", "description", "descriptions",
    "instance", "instances", "create", "creates", "creating", "build", "implement",
    "provide", "provides", "providing", "allow", "allows", "allowing", "allowed",
    "enable", "enables", "support", "supports",
    "manage", "manages", "managing", "management", "monitor", "monitors", "monitoring",
    "register", "registers", "registering", "registration",
    "across", "multiple", "receive", "receives", "receiving", "based",
    "like", "just", "make", "made", "does", "doing", "done", "demo", "sample",
    "example", "please", "thanks", "intent", "domain", "application",
    "infrastructure", "service", "repository", "model", "view", "snapshot",
    "detected", "language", "technical", "specification", "reverse", "engineered",
    "structural", "provided", "collaborate", "dependencies", "callable", "orchestration",
    "unknown", "primary", "process", "processes", "processing", "variable", "state",
    "modules", "true", "false", "active", "status", "name", "string", "float", "boolean",
    "date", "notes", "flag", "title", "priority", "ownerid", "createdat",
    "associates", "depends", "composition", "modules", "core",
    "then", "than", "such", "etc", "via", "per", "within", "without", "upon",
    "limits", "limit", "offerings", "offering", "reminders", "reminder",
    "confirm", "confirms", "confirming", "assign", "assigns", "assigning",
    "complete", "completes", "completing", "cancel", "cancels", "cancelled",
    "notify", "notifies", "notifying", "submit", "submits", "submitting",
    "update", "updates", "updating", "delete", "deletes", "deleting",
    "perform", "performs", "performing", "related", "regarding", "including",
}


def _strip_prompt_meta(body: str) -> str:
    """Drop template trails like 'Target diagram type:' from focused bodies."""
    body = re.split(r"(?im)^\s*Target diagram type:\s*", body, maxsplit=1)[0]
    body = re.split(r"(?im)^\s*Validation errors:\s*", body, maxsplit=1)[0]
    return body.strip()


def _content_focus(text: str) -> str:
    """Prefer the user/spec body over prompt-template prose."""
    markers = [
        r"Technical specification:\s*",
        r"Software requirement:\s*",
        r"Source code:\s*",
        r"Broken PlantUML:\s*",
        r"Original technical specification:\s*",
    ]
    for marker in markers:
        m = re.search(marker, text, flags=re.I)
        if m:
            body = _strip_prompt_meta(text[m.end() :].strip())
            from_source = "from source code" in body.lower()
            if not from_source:
                ents = re.findall(r"^-\s*([A-Za-z][A-Za-z0-9_]+)\s*:", body, flags=re.M)
                if len(ents) >= 2:
                    return " ".join(ents) + "\n" + body
                intent = re.search(
                    r"###\s*Source intent\s*\n(.+?)(?:\n###|\Z)",
                    body,
                    flags=re.I | re.S,
                )
                if intent:
                    return _strip_prompt_meta(intent.group(1).strip())
            return body
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > 3 and lines[0].lower().startswith("you "):
        return _strip_prompt_meta("\n".join(lines[3:]).strip() or text)
    return _strip_prompt_meta(text.strip())


def _title_entity(raw: str) -> str | None:
    """Normalize a candidate token into a PascalCase entity name."""
    title = re.sub(r"[^A-Za-z0-9]", "", raw)
    if not title or len(title) < 3:
        return None
    title = title[0].upper() + title[1:]
    if title.endswith("ies") and len(title) > 4:
        title = title[:-3] + "y"
    elif title.endswith("s") and not title.endswith("ss") and len(title) > 4:
        title = title[:-1]
    if title.lower() in _STOP:
        return None
    return title


# Prefer domain noun fillers over generic EntityN when padding
_DOMAIN_FILLERS = [
    "Enrollment",
    "Payment",
    "Session",
    "Profile",
    "Ticket",
    "Notification",
    "Account",
]


def _entities_from_requirement_roles(text: str, n: int = 5) -> list[str] | None:
    """
    Pull domain actors/objects from requirement prose.

    Patterns: 'students to register', 'for courses', 'with doctors',
    'to monitor enrollment'.
    """
    names: list[str] = []

    def _add(raw: str) -> None:
        ent = _title_entity(raw)
        if ent and ent not in names:
            names.append(ent)

    for raw in re.findall(r"\b([A-Za-z][a-z]{2,})\s+to\s+[a-z]+\b", text):
        _add(raw)
    for raw in re.findall(
        r"\b(?:for|with|across|of|via|using)\s+([A-Za-z][a-z]{2,})\b", text, flags=re.I
    ):
        _add(raw)
    # Object of an infinitive verb phrase: "to monitor enrollment"
    for raw in re.findall(r"\bto\s+[a-z]{2,}\s+([A-Za-z][a-z]{3,})\b", text):
        _add(raw)
    # Capitalized multi-word domain nouns already present
    for raw in re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text):
        _add(raw)

    if len(names) < 2:
        return None
    fi = 0
    while len(names) < n:
        filler = _DOMAIN_FILLERS[fi % len(_DOMAIN_FILLERS)]
        if filler not in names:
            names.append(filler)
        else:
            names.append(f"Entity{len(names) + 1}")
        fi += 1
    return names[:n]


def _detect_diagram_type(system: str, user: str) -> str:
    """Detect diagram type from prompt instructions only (not from generated spec)."""
    head = user
    for sep in ("Technical specification:", "Software requirement:", "Broken PlantUML:"):
        idx = user.lower().find(sep.lower())
        if idx != -1:
            head = user[:idx]
            break
    blob = f"{system}\n{head}".lower()
    if re.search(r"for an?\s+object\s+diagram|object diagram", blob):
        return "object"
    if re.search(r"for an?\s+component\s+diagram|component diagram", blob):
        return "component"
    if re.search(r"for an?\s+package\s+diagram|package diagram", blob):
        return "package"
    if re.search(r"flowchart|activity diagram", blob):
        return "flowchart"
    if re.search(r"for an?\s+class\s+diagram|class diagram", blob):
        return "class"
    return "class"


def _entities_from_entities_section(text: str, n: int = 5) -> list[str] | None:
    """Parse ### Entities bullets before stripping that section away."""
    section = re.search(r"###\s*Entities\s*\n(.*?)(?:\n###|\Z)", text, flags=re.I | re.S)
    if not section:
        return None
    names: list[str] = []
    for line in section.group(1).splitlines():
        match = re.match(r"^-\s*([A-Za-z_]\w*)\s*:", line.strip())
        if not match:
            continue
        name = match.group(1)
        if name.lower() in {"domain", "application", "infrastructure", "python", "java", "javascript", "unknown"}:
            continue
        if name.islower() and name.isidentifier():
            name = name[0].upper() + name[1:]
        if name not in names:
            names.append(name)
    if not names:
        return None
    while len(names) < n:
        names.append(f"Module{len(names)+1}")
    return names[:n]


def _strip_spec_boilerplate(text: str) -> str:
    """Drop auto-generated spec headings so entity extraction stays on user content."""
    m = re.search(r"source code:\s*", text, flags=re.I)
    if m:
        return text[m.end() :].strip()
    cleaned: list[str] = []
    skip_prefixes = (
        "## technical specification",
        "### detected language",
        "### source intent",
        "### entities",
        "### modules",
        "### relationships",
        "### imports",
        "### process steps",
    )
    for line in text.splitlines():
        low = line.strip().lower()
        if any(low.startswith(p) for p in skip_prefixes):
            continue
        if re.match(r"^-\s*(domain|application|infrastructure|unknown|python|java|javascript)\s*:?\s*$", low):
            continue
        if re.match(r"^-\s*(domain|application|infrastructure)\s*:", low):
            continue
        if "reverse-engineered structural model" in low:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip() or text


def _entities_from_text(text: str, n: int = 5) -> list[str]:
    from app.services.code_analysis import analyze_source_code, looks_like_source_code

    raw_focus = _content_focus(text)
    from_section = _entities_from_entities_section(raw_focus, n=n)
    if from_section:
        return from_section

    focus = _strip_spec_boilerplate(raw_focus)

    if looks_like_source_code(focus) or "source code:" in text.lower():
        names = analyze_source_code(focus).entity_names(n=n)
        if names and not all(x.startswith("Module") for x in names):
            return names

    # Prefer bullet entity names from structured specs
    bullet_ents = re.findall(r"(?m)^-\s*([A-Za-z][A-Za-z0-9_]+)\s*:", focus)
    skip_headers = {
        "domain",
        "application",
        "infrastructure",
        "python",
        "java",
        "javascript",
        "unknown",
    }
    bullet_ents = [e for e in bullet_ents if e.lower() not in skip_headers]
    if len(bullet_ents) >= 2:
        out = list(dict.fromkeys(bullet_ents))
        while len(out) < n:
            out.append(f"Entity{len(out)+1}")
        return out[:n]

    # Requirement prose: prefer actor/object roles over modal/verb tokens
    from_roles = _entities_from_requirement_roles(focus, n=n)
    if from_roles:
        return from_roles

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", focus)
    uniq: list[str] = []
    for w in words:
        title = _title_entity(w)
        if not title:
            continue
        if title not in uniq:
            uniq.append(title)
        if len(uniq) >= n:
            break

    if len(uniq) < n:
        digest = hashlib.sha256(focus.encode()).hexdigest()
        fillers = ["Account", "Order", "Session", "Profile", "Ticket", "Device", "Payment"]
        i = 0
        while len(uniq) < n:
            idx = int(digest[i * 2 : i * 2 + 2], 16) % len(fillers)
            # Prefix with content-derived syllable so fillers still differ by input
            prefix = re.sub(r"[^A-Za-z]", "", focus)[:3].title() or "App"
            name = f"{prefix}{fillers[idx]}"
            if name not in uniq:
                uniq.append(name)
            i += 1
            if i > 30:
                uniq.append(f"Entity{len(uniq)+1}")
    return uniq[:n]


def _attrs_for(entity: str, seed: str) -> list[str]:
    h = int(hashlib.sha256((entity + seed).encode()).hexdigest(), 16)
    pools = [
        ["id: int", "name: string", "status: string"],
        ["id: int", "createdAt: date", "active: boolean"],
        ["code: string", "title: string", "priority: int"],
        ["id: int", "ownerId: int", "notes: string"],
    ]
    return pools[h % len(pools)]


class MockProvider:
    name = "mock"
    model = "mock-local"

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        lower = (system + "\n" + user).lower()
        if "repair" in lower or "broken plantuml" in lower:
            return self._repair(system, user)
        dtype = _detect_diagram_type(system, user)
        # Distinguish "generate PlantUML" from prompts that merely mention it,
        # such as "Do NOT output PlantUML" in technical-spec instructions.
        plantuml_generation = (
            "@startuml" in lower
            or "output only valid plantuml" in lower
            or "convert the technical specification into syntactically valid plantuml" in lower
            or "then output only final plantuml" in lower
            or "uml expert" in system.lower()
            or "chain-of-thought (required)" in lower
            or "inside <think>" in lower
            or "after </think>" in lower
            or "<think>" in system.lower()
        )
        if plantuml_generation:
            code = self._plantuml(user, dtype)
            if (
                "chain-of-thought (required)" in lower
                or "inside <think>" in lower
                or "after </think>" in lower
                or "<think>" in system.lower()
            ):
                return (
                    "<think>\n"
                    f"Identify entities from the specification for a {dtype} diagram, "
                    "choose connectors, and validate hierarchy before emitting PlantUML.\n"
                    "</think>\n"
                    f"{code}"
                )
            return code
        return self._spec(user)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self.vision_assess(image_path, prompt).score

    def vision_assess(self, image_path: Path, prompt: str):
        from uml_pipeline.llm_client import VisionAssessment

        data = image_path.read_bytes() if image_path.is_file() else b"0"
        focus = _content_focus(prompt)
        h = int(hashlib.sha256(data + focus.encode()).hexdigest(), 16)
        score = 3 + (h % 3)
        explanation = (
            f"Mock VLM: semantic alignment looks moderate-to-strong (score {score}/6); "
            "structure covers main entities from the specification; notation appears valid; "
            "layout is coherent for evaluation purposes."
        )
        raw = f"SCORE: {score}\nEXPLANATION: {explanation}"
        return VisionAssessment(score=score, explanation=explanation, raw_output=raw)

    def _spec(self, user: str) -> str:
        import json

        from app.services.code_analysis import looks_like_source_code, structure_to_spec
        from app.services.spec_json import ensure_valid_spec, heuristic_spec_from_text

        focus = _content_focus(user)
        dtype = "class"
        m = re.search(r"Target diagram type:\s*(\w+)", user, flags=re.I)
        if m:
            dtype = m.group(1).lower()
        if "source code:" in user.lower() or looks_like_source_code(focus):
            prose = structure_to_spec(focus, dtype)
            data, _, _ = ensure_valid_spec(prose, dtype)
            return json.dumps(data, indent=2)

        entities = _entities_from_text(user, n=5)
        a, b, c, d, e = entities
        data = heuristic_spec_from_text(
            f"- {a}: core\n- {b}: related\n- {c}: related\n"
            f"- {a} associates with {b}\n- {a} composition of {c}\n"
            f"- {d} depends on {b}\n- {e} associates with {a}\n"
            f"1. Start {a}\n2. Validate {b}\n3. Process {d}\n4. Finish\n"
            f"{focus[:400]}",
            dtype,
        )
        data["summary"] = f"Mock Stage-1 spec for {dtype} involving {a}, {b}, {c}"
        data["entities"] = [
            {
                "name": ent,
                "kind": "class",
                "attributes": _attrs_for(ent, focus)[:4],
                "methods": ["process()"],
            }
            for ent in entities
        ]
        data["relationships"] = [
            {"source": a, "target": b, "type": "association", "label": "uses"},
            {"source": a, "target": c, "type": "composition", "label": ""},
            {"source": d, "target": b, "type": "dependency", "label": ""},
            {"source": e, "target": a, "type": "association", "label": ""},
        ]
        if dtype == "flowchart":
            data["process_steps"] = [
                f"Receive request for {a}",
                f"Validate {b}",
                f"Decide on {c}",
                f"Process {d}",
                f"Notify about {a}",
            ]
        return json.dumps(data, indent=2)

    def _plantuml(self, user: str, diagram_type: str) -> str:
        from app.services.plantuml_from_spec import plantuml_from_spec
        from app.services.spec_json import ensure_valid_spec

        focus = _content_focus(user)
        # Ground mock diagrams in Stage-1 JSON so names match the requirement/code
        mode = "source_code" if "source code:" in user.lower() else "requirement"
        spec, _, _ = ensure_valid_spec(focus, diagram_type, source_text=focus, input_mode=mode)
        # Enrich class attrs when missing so diagrams look complete in demos
        if diagram_type == "class":
            for ent in spec.get("entities") or []:
                if isinstance(ent, dict) and not ent.get("attributes"):
                    ent["attributes"] = _attrs_for(str(ent.get("name") or "Entity"), focus)
        return plantuml_from_spec(spec, diagram_type)

    def _repair(self, system: str, user: str) -> str:
        dtype = _detect_diagram_type(system, user)
        focus = _content_focus(user)
        entities = _entities_from_text(user, n=3)
        a, b, c = entities
        if dtype == "package" or "package" in user.lower()[:400]:
            return (
                "@startuml\n"
                "package domain {\n"
                f"  class {a}\n"
                f"  class {b}\n"
                "}\n"
                "package application {\n"
                f"  class {c}Service\n"
                "}\n"
                "application ..> domain : uses\n"
                "@enduml"
            )
        m = re.search(r"@startuml.*?@enduml", user, flags=re.I | re.S)
        if m:
            code = re.sub(r"(?m)^\s*(\w+)\s+\.\.>\s*\1\s*.*$", "", m.group(0))
            return code
        return (
            "@startuml\n"
            f"class {a} {{\n  +id: int\n}}\n"
            f"class {b} {{\n  +name: string\n}}\n"
            f"{a} --> {b}\n"
            "@enduml"
        )
