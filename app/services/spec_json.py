"""Stage-1 technical specification as paper-faithful JSON + validity checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


REQUIRED_TOP_LEVEL = ("diagram_type", "entities", "relationships")
VALID_REL_TYPES = {
    "association",
    "aggregation",
    "composition",
    "inheritance",
    "dependency",
    "containment",
    "realization",
    "link",
    "uses",
}


@dataclass
class SpecValidation:
    ok: bool
    messages: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output (raw or fenced)."""
    if not text or not text.strip():
        return None
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def validate_spec_json(data: Any, diagram_type: str | None = None) -> SpecValidation:
    msgs: list[str] = []
    if not isinstance(data, dict):
        return SpecValidation(ok=False, messages=["Specification is not a JSON object"])

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            msgs.append(f"Missing required field: {key}")

    dtype = str(data.get("diagram_type") or diagram_type or "").lower().strip()
    if not dtype:
        msgs.append("Missing diagram_type")
    elif diagram_type and dtype != diagram_type.lower():
        # Soft-correct later; warn only
        msgs.append(f"diagram_type mismatch (got {dtype}, expected {diagram_type})")

    entities = data.get("entities")
    if not isinstance(entities, list) or len(entities) < 1:
        msgs.append("entities must be a non-empty list")
    else:
        for i, ent in enumerate(entities):
            if not isinstance(ent, dict) or not str(ent.get("name") or "").strip():
                msgs.append(f"entities[{i}] needs a name")
                break

    rels = data.get("relationships")
    if not isinstance(rels, list):
        msgs.append("relationships must be a list")
    elif len(rels) < 1 and dtype != "flowchart":
        msgs.append("relationships should include at least one link for structural UML")

    if dtype == "flowchart":
        steps = data.get("process_steps") or data.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            msgs.append("flowchart specs need process_steps with at least 2 steps")

    # Hard failures vs soft warnings: mismatch is soft if everything else OK
    hard = [
        m
        for m in msgs
        if not m.startswith("diagram_type mismatch")
        and "should include at least one link" not in m
    ]
    # Require entities always; relationships required except we allow empty with soft msg
    ok = len(hard) == 0 and isinstance(entities, list) and len(entities) >= 1
    if ok and diagram_type:
        data = dict(data)
        data["diagram_type"] = diagram_type.lower()
    return SpecValidation(ok=ok, messages=msgs, data=data if isinstance(data, dict) else {})


def spec_to_prose(data: dict[str, Any]) -> str:
    """Deterministic prose view of JSON for Stage-2 prompts and VLM context."""
    dtype = str(data.get("diagram_type") or "class")
    lines = [
        "## Technical Specification (JSON Stage-1)",
        f"### Diagram type\n- {dtype}",
    ]
    summary = str(data.get("summary") or "").strip()
    if summary:
        lines.append(f"### Summary\n{summary}")

    lines.append("### Entities")
    for ent in data.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        name = ent.get("name") or "Entity"
        kind = ent.get("kind") or "class"
        attrs = ent.get("attributes") or []
        methods = ent.get("methods") or []
        detail = []
        if attrs:
            detail.append("attrs: " + ", ".join(str(a) for a in attrs[:12]))
        if methods:
            detail.append("methods: " + ", ".join(str(m) for m in methods[:12]))
        suffix = f" ({'; '.join(detail)})" if detail else ""
        lines.append(f"- {name}: {kind}{suffix}")

    lines.append("### Relationships")
    rels = data.get("relationships") or []
    if not rels:
        lines.append("- (none specified)")
    for rel in rels:
        if not isinstance(rel, dict):
            continue
        src = rel.get("source") or "?"
        tgt = rel.get("target") or "?"
        rtype = rel.get("type") or "association"
        label = rel.get("label") or ""
        extra = f" ({label})" if label else ""
        lines.append(f"- {src} --{rtype}--> {tgt}{extra}")

    constraints = data.get("constraints") or []
    if constraints:
        lines.append("### Constraints")
        for c in constraints:
            lines.append(f"- {c}")

    packages = data.get("packages") or []
    if packages:
        lines.append("### Packages")
        for p in packages:
            if isinstance(p, dict):
                lines.append(f"- {p.get('name')}: contains {', '.join(p.get('contains') or [])}")
            else:
                lines.append(f"- {p}")

    components = data.get("components") or []
    if components:
        lines.append("### Components")
        for c in components:
            if isinstance(c, dict):
                lines.append(f"- {c.get('name')}: {', '.join(c.get('interfaces') or [])}")
            else:
                lines.append(f"- {c}")

    objects = data.get("objects") or []
    if objects:
        lines.append("### Objects")
        for o in objects:
            if isinstance(o, dict):
                lines.append(f"- {o.get('name')}:{o.get('type') or 'Object'}")
            else:
                lines.append(f"- {o}")

    steps = data.get("process_steps") or data.get("steps") or []
    if steps:
        lines.append("### Process steps")
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                lines.append(f"{i}. {step.get('name') or step.get('action') or step}")
            else:
                lines.append(f"{i}. {step}")

    return "\n".join(lines).strip() + "\n"


def heuristic_spec_from_text(text: str, diagram_type: str) -> dict[str, Any]:
    """Build a minimal valid JSON spec from prose/code-analysis bullets when LLM JSON fails."""
    entities: list[dict[str, Any]] = []
    for m in re.finditer(r"(?m)^-\s*([A-Za-z_][\w]*)\s*:", text):
        name = m.group(1)
        if name.lower() in {"id", "name", "string", "int", "float"}:
            continue
        if not any(e["name"] == name for e in entities):
            entities.append({"name": name, "kind": "class", "attributes": [], "methods": []})

    # PascalCase tokens in free text
    if len(entities) < 2:
        for tok in re.findall(r"\b([A-Z][a-zA-Z0-9]{2,})\b", text):
            if tok.lower() in {"the", "and", "for", "with", "this", "that", "uml", "json"}:
                continue
            if not any(e["name"] == tok for e in entities):
                entities.append({"name": tok, "kind": "class", "attributes": [], "methods": []})
            if len(entities) >= 5:
                break

    if not entities:
        entities = [
            {"name": "EntityA", "kind": "class", "attributes": ["id: int"], "methods": []},
            {"name": "EntityB", "kind": "class", "attributes": ["name: string"], "methods": []},
        ]

    relationships: list[dict[str, Any]] = []
    for m in re.finditer(
        r"(?i)([A-Za-z_]\w*)\s+(inherits|extends|associates with|depends on|uses|contains)\s+([A-Za-z_]\w*)",
        text,
    ):
        mapping = {
            "inherits": "inheritance",
            "extends": "inheritance",
            "associates with": "association",
            "depends on": "dependency",
            "uses": "dependency",
            "contains": "containment",
        }
        relationships.append(
            {
                "source": m.group(1),
                "target": m.group(3),
                "type": mapping.get(m.group(2).lower(), "association"),
            }
        )
    if not relationships and len(entities) >= 2:
        relationships.append(
            {
                "source": entities[0]["name"],
                "target": entities[1]["name"],
                "type": "association",
            }
        )

    steps = []
    for m in re.finditer(r"(?m)^\d+\.\s*(.+)$", text):
        steps.append(m.group(1).strip())

    data: dict[str, Any] = {
        "diagram_type": diagram_type,
        "summary": (text.strip().splitlines()[0] if text.strip() else "")[:240],
        "entities": entities[:12],
        "relationships": relationships[:20],
        "constraints": [],
    }
    if diagram_type == "flowchart":
        data["process_steps"] = steps[:12] or [e["name"] for e in entities[:4]] + ["Complete"]
    if diagram_type == "package":
        data["packages"] = [
            {"name": "core", "contains": [e["name"] for e in entities[:3]]},
            {"name": "api", "contains": [entities[-1]["name"]]},
        ]
    if diagram_type == "component":
        data["components"] = [{"name": e["name"] + "Service", "interfaces": ["I" + e["name"]]} for e in entities[:3]]
    if diagram_type == "object":
        data["objects"] = [{"name": e["name"].lower() + "1", "type": e["name"]} for e in entities[:4]]
    return data


_STOP_ENTITY = {
    "the", "and", "for", "with", "from", "that", "this", "your", "system", "software",
    "class", "classes", "object", "component", "package", "diagram", "uml", "json",
    "service", "services", "module", "modules", "using", "through", "into", "via",
    "must", "should", "shall", "will", "have", "has", "been", "being", "also",
    "build", "create", "manage", "management", "application", "platform", "model",
}


def extract_named_concepts(text: str) -> list[str]:
    """Pull likely domain entity names from NL or mixed text (professional grounding)."""
    names: list[str] = []
    reject = _STOP_ENTITY | {
        "svc", "api", "store", "repo", "alice", "bob", "carol", "dave", "main",
        "ecommerce", "banking", "hospital", "library", "checkout", "online",
    }

    def _add(raw: str) -> None:
        name = re.sub(r"[^A-Za-z0-9_]", "", raw or "")
        if len(name) < 3 or name.lower() in reject:
            return
        if name.lower() in {"service", "services", "component", "components", "package", "packages"}:
            return
        if name[0].islower():
            name = name[0].upper() + name[1:]
        if name not in names:
            names.append(name)

    # "patient Alice (Patient)" / "doctor Bob (Doctor)" — keep type in parentheses
    for m in re.finditer(r"\(([A-Z][A-Za-z0-9_]*)\)", text):
        _add(m.group(1))

    # Explicit lists: "classes Book, Member, and Librarian" / "components: A, B, C"
    for m in re.finditer(
        r"(?i)\b(?:classes?|entities|components?|packages?|modules?|types?)\b"
        r"[:\s]+([^\n.;]+)",
        text,
    ):
        chunk = m.group(1)
        # Cut trailing sentence after the list (e.g. ". A Member borrows...")
        chunk = re.split(r"[.]", chunk)[0]
        for part in re.split(r"\s*,\s*|\s*&\s*", chunk):
            part = re.sub(r"(?i)^\s*and\s+", "", part.strip().strip("."))
            if not part or part.lower() in {"and", "or", "with"}:
                continue
            _add(part)

    # "with Book, Member, Loan"
    for m in re.finditer(
        r"(?i)\b(?:with|including|involving)\s+([A-Z][A-Za-z0-9_]*(?:\s*,\s*[A-Z][A-Za-z0-9_]*)+"
        r"(?:\s*,?\s*(?:and|&)\s*[A-Z][A-Za-z0-9_]*)?)",
        text,
    ):
        for part in re.split(r"\s*,\s*|\s+and\s+|\s*&\s*", m.group(1)):
            _add(part.strip())

    # CamelCase / PascalCase service-style tokens (CartService) — prefer these
    for tok in re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-zA-Z0-9]+)+)\b", text):
        _add(tok)

    # Single Pascal tokens only if we still have few names
    if len(names) < 3:
        for tok in re.findall(r"\b([A-Z][a-zA-Z]{2,})\b", text):
            if tok.lower() not in reject:
                _add(tok)

    # Quoted names
    for tok in re.findall(r"['\"]([A-Za-z][\w]+)['\"]", text):
        _add(tok)

    return names[:16]


def _singularize_token(name: str) -> str:
    if len(name) > 3 and name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def extract_nl_relationships(text: str) -> list[dict[str, Any]]:
    """Lightweight NL relation mining for Stage-1 grounding."""
    rels: list[dict[str, Any]] = []
    patterns = [
        (r"(?i)\b([A-Z][\w]*)\s+borrows?\s+(?:a\s+)?([A-Z][\w]*)\s+through\s+(?:a\s+)?([A-Z][\w]*)",
         lambda m: [
             {"source": m.group(1), "target": m.group(3), "type": "association", "label": "creates"},
             {"source": m.group(3), "target": m.group(2), "type": "association", "label": "for"},
         ]),
        (r"(?i)\b([A-Z][\w]*)\s+manages?\s+([A-Z][\w]*)",
         lambda m: [{"source": m.group(1), "target": _singularize_token(m.group(2)), "type": "association", "label": "manages"}]),
        (r"(?i)\b([A-Z][\w]*)\s+depends\s+on\s+([A-Z][\w]*)",
         lambda m: [{"source": m.group(1), "target": m.group(2), "type": "dependency", "label": "depends"}]),
        (r"(?i)\b([A-Z][\w]*)\s+(?:uses|links\s+to|associated\s+with)\s+([A-Z][\w]*)",
         lambda m: [{"source": m.group(1), "target": m.group(2), "type": "association", "label": "uses"}]),
    ]
    for pat, builder in patterns:
        for m in re.finditer(pat, text):
            rels.extend(builder(m))
    return rels


def structure_to_spec_json(code: str, diagram_type: str) -> dict[str, Any]:
    """Authoritative Stage-1 JSON recovered from source code structure."""
    from app.services.code_analysis import analyze_source_code

    s = analyze_source_code(code)
    entities = []
    for c in s.classes:
        entities.append(
            {
                "name": c,
                "kind": "class",
                "attributes": [],
                "methods": list(s.methods.get(c) or [])[:12],
            }
        )
    # Never invent classes from variables / string literals when none are declared
    relationships: list[dict[str, Any]] = []
    for child, parents in s.bases.items():
        for p in parents:
            relationships.append({"source": child, "target": p, "type": "inheritance", "label": ""})
    if s.classes:
        for m in re.finditer(
            r"(?i)(\w+)\s*\([^)]*\b([A-Z][A-Za-z0-9_]*)\b[^)]*\)",
            code,
        ):
            src_ctx, typ = m.group(1), m.group(2)
            owner = next((c for c in s.classes if c in code[max(0, m.start() - 80) : m.start()]), None)
            if owner and typ in s.classes and owner != typ:
                relationships.append({"source": owner, "target": typ, "type": "association", "label": src_ctx})
        for m in re.finditer(
            r"(?i)(private|protected|public)\s+([A-Z][A-Za-z0-9_]*)\s+(\w+)\s*;",
            code,
        ):
            typ, _field = m.group(2), m.group(3)
            before = code[: m.start()]
            cls = re.findall(r"(?i)class\s+(\w+)", before)
            if cls and typ in s.classes and cls[-1] != typ:
                relationships.append({"source": cls[-1], "target": typ, "type": "association", "label": _field})
        for m in re.finditer(
            r"(?i)(?:public|private|protected)?\s*(?:[\w<>\[\]]+\s+)?(\w+)\s*\(\s*([A-Z][A-Za-z0-9_]*)\s+\w+",
            code,
        ):
            typ = m.group(2)
            before = code[: m.start()]
            cls = re.findall(r"(?i)class\s+(\w+)", before)
            if cls and typ in s.classes and cls[-1] != typ:
                relationships.append({"source": cls[-1], "target": typ, "type": "association", "label": m.group(1)})
        if not relationships and len(entities) >= 2:
            relationships.append(
                {"source": entities[0]["name"], "target": entities[1]["name"], "type": "association", "label": ""}
            )

    seen = set()
    uniq = []
    for r in relationships:
        key = (r["source"], r["target"], r["type"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)

    script_without_types = not s.has_type_declarations
    effective_type = diagram_type

    data: dict[str, Any] = {
        "diagram_type": effective_type,
        "summary": (
            f"Script/driver with no class declarations ({s.language})"
            if script_without_types
            else f"Design recovered from {s.language} source ({len(entities)} types)"
        ),
        "entities": entities[:12],
        "relationships": uniq[:20],
        "constraints": (
            [
                "Source has no class/interface declarations",
                "Do not treat variables or string paths as UML classes",
            ]
            if script_without_types
            else []
        ),
        "script_without_types": script_without_types,
        "requested_diagram_type": diagram_type,
    }
    steps = s.script_process_steps(code)
    if script_without_types:
        data["process_steps"] = steps or [
            "Import dependencies",
            "Configure parameters",
            "Run main logic",
            "Write outputs",
        ]
    if diagram_type == "object" and entities:
        data["objects"] = [
            {"name": e["name"][:1].lower() + e["name"][1:] + "1", "type": e["name"]} for e in entities[:5]
        ]
        data["diagram_type"] = "object"
    if diagram_type == "component" and not script_without_types:
        data["components"] = [{"name": e["name"], "interfaces": ["I" + e["name"]]} for e in entities[:6]]
    if diagram_type == "package" and not script_without_types:
        data["packages"] = [{"name": e["name"], "contains": [e["name"]]} for e in entities[:6]]
    if diagram_type == "component" and script_without_types:
        # Honest component view: this script + imported libraries
        comps = ["DriverScript"]
        for imp in s.imports[:4]:
            m = re.search(r"(?:import|from)\s+([\w.]+)", imp)
            if m:
                comps.append(m.group(1).split(".")[0])
        data["components"] = [{"name": c, "interfaces": []} for c in list(dict.fromkeys(comps))[:6]]
        data["relationships"] = [
            {"source": "DriverScript", "target": c, "type": "dependency", "label": "uses"}
            for c in comps[1:4]
        ]
        data["diagram_type"] = "component"
        data["process_steps"] = steps
    return data


def merge_spec_entities(base: dict[str, Any], extra_names: list[str], diagram_type: str) -> dict[str, Any]:
    """Ensure required concept names appear in the Stage-1 JSON."""
    data = dict(base)
    entities = [e for e in (data.get("entities") or []) if isinstance(e, dict)]
    # Drop placeholder entities once real domain names are known
    if extra_names:
        entities = [
            e
            for e in entities
            if not re.match(r"^(Entity[A-Z]?\d*|Module\d+|Class\d+)$", str(e.get("name") or ""), re.I)
        ]
    have = {str(e.get("name") or "").lower() for e in entities}
    for name in extra_names:
        if name.lower() in have:
            continue
        entities.append({"name": name, "kind": "class", "attributes": [], "methods": []})
        have.add(name.lower())
    data["entities"] = entities
    if diagram_type == "component":
        comps = list(data.get("components") or [])
        have_c = {
            (c.get("name") if isinstance(c, dict) else str(c)).lower()
            for c in comps
        }
        for name in extra_names:
            if name.lower() in have_c:
                continue
            comps.append({"name": name, "interfaces": ["I" + re.sub(r"(Service|Api)$", "", name)]})
            have_c.add(name.lower())
        data["components"] = comps
    if diagram_type == "package":
        generic_layers = {"domain", "application", "infrastructure", "core", "api"}
        named = [n for n in extra_names if n.lower() not in generic_layers]
        if named:
            # Prefer explicit domain package names from the requirement
            data["packages"] = [{"name": n, "contains": [n]} for n in named[:8]]
        else:
            pkgs = [p for p in (data.get("packages") or []) if isinstance(p, dict)]
            have_p = {str(p.get("name") or "").lower() for p in pkgs}
            for name in extra_names:
                if name.lower() in have_p:
                    continue
                pkgs.append({"name": name, "contains": [name]})
                have_p.add(name.lower())
            data["packages"] = pkgs
    if diagram_type == "object":
        objs = list(data.get("objects") or [])
        have_t = {
            str(o.get("type") if isinstance(o, dict) else "").lower() for o in objs
        }
        for name in extra_names:
            if name.lower() in have_t:
                continue
            objs.append({"name": name[:1].lower() + name[1:] + "1", "type": name})
            have_t.add(name.lower())
        data["objects"] = objs
    # relationships among consecutive required names if sparse
    rels = [r for r in (data.get("relationships") or []) if isinstance(r, dict)]
    if len(rels) < max(1, len(extra_names) - 1) and len(extra_names) >= 2:
        for a, b in zip(extra_names, extra_names[1:]):
            rels.append({"source": a, "target": b, "type": "association", "label": ""})
    data["relationships"] = rels[:20]
    data["diagram_type"] = diagram_type
    return data


def ensure_valid_spec(
    raw_text: str,
    diagram_type: str,
    *,
    source_text: str | None = None,
    input_mode: str = "requirement",
) -> tuple[dict[str, Any], str, list[str]]:
    """
    Parse/validate Stage-1 JSON; fall back to heuristic conversion.
    Merges named concepts from the original requirement/code for fidelity.
    Returns (json_dict, prose_text, validity_messages).
    """
    messages: list[str] = []
    grounding = source_text or raw_text

    if input_mode == "source_code":
        data = structure_to_spec_json(grounding, diagram_type)
        parsed = extract_json_object(raw_text)
        # Only enrich attributes/methods on *declared* classes — never add LLM-invented types
        if (
            parsed
            and isinstance(parsed.get("entities"), list)
            and not data.get("script_without_types")
        ):
            by_name = {e["name"].lower(): e for e in data["entities"] if e.get("name")}
            declared = set(by_name)
            for ent in parsed["entities"]:
                if not isinstance(ent, dict) or not ent.get("name"):
                    continue
                key = str(ent["name"]).lower()
                if key in by_name:
                    if ent.get("methods") and not by_name[key].get("methods"):
                        by_name[key]["methods"] = ent.get("methods")
                    if ent.get("attributes") and not by_name[key].get("attributes"):
                        by_name[key]["attributes"] = ent.get("attributes")
                elif key in declared:
                    continue
                # Ignore undeclared names (variables / string tokens / hallucinations)
        if data.get("script_without_types"):
            messages.append(
                "Source has no class/interface declarations — not inventing UML classes "
                "from variables"
            )
        else:
            messages.append("Stage-1 grounded in source-code structure analysis")
        prose = spec_to_prose(data)
        return data, prose, messages

    parsed = extract_json_object(raw_text)
    if parsed is not None:
        result = validate_spec_json(parsed, diagram_type)
        if result.ok:
            data = result.data
            messages.extend(result.messages)
        else:
            messages.extend(result.messages)
            messages.append("Falling back to heuristic JSON from model text")
            data = heuristic_spec_from_text(raw_text, diagram_type)
            if isinstance(parsed.get("entities"), list):
                data = merge_spec_entities(
                    data,
                    [str(e.get("name")) for e in parsed["entities"] if isinstance(e, dict) and e.get("name")],
                    diagram_type,
                )
    else:
        messages.append("Model output was not valid JSON; building heuristic Stage-1 JSON")
        data = heuristic_spec_from_text(raw_text, diagram_type)

    concepts = extract_named_concepts(grounding)
    if concepts:
        data = merge_spec_entities(data, concepts, diagram_type)
        messages.append(f"Merged grounded concepts: {', '.join(concepts[:8])}")
    nl_rels = extract_nl_relationships(grounding)
    if nl_rels:
        rels = [r for r in (data.get("relationships") or []) if isinstance(r, dict)]
        seen = {(r.get("source"), r.get("target"), r.get("type")) for r in rels}
        for r in nl_rels:
            key = (r.get("source"), r.get("target"), r.get("type"))
            if key not in seen:
                rels.append(r)
                seen.add(key)
        data["relationships"] = rels[:20]

    result = validate_spec_json(data, diagram_type)
    prose = spec_to_prose(result.data if result.ok else data)
    if not result.ok:
        messages.extend(result.messages)
    return (result.data if result.ok else data), prose, messages


def validity_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """Simple Stage-1 validity metrics for logging / thesis tables."""
    entities = data.get("entities") or []
    rels = data.get("relationships") or []
    named = sum(1 for e in entities if isinstance(e, dict) and e.get("name"))
    typed_rels = sum(
        1
        for r in rels
        if isinstance(r, dict) and str(r.get("type") or "").lower() in VALID_REL_TYPES
    )
    return {
        "entity_count": len(entities),
        "named_entity_count": named,
        "relationship_count": len(rels),
        "typed_relationship_count": typed_rels,
        "has_summary": bool(str(data.get("summary") or "").strip()),
        "json_valid": named >= 1 and len(entities) >= 1,
    }
