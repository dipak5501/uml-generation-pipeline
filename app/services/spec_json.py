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


def ensure_valid_spec(raw_text: str, diagram_type: str) -> tuple[dict[str, Any], str, list[str]]:
    """
    Parse/validate Stage-1 JSON; fall back to heuristic conversion.
    Returns (json_dict, prose_text, validity_messages).
    """
    messages: list[str] = []
    parsed = extract_json_object(raw_text)
    if parsed is not None:
        result = validate_spec_json(parsed, diagram_type)
        if result.ok:
            prose = spec_to_prose(result.data)
            return result.data, prose, result.messages
        messages.extend(result.messages)
        messages.append("Falling back to heuristic JSON from model text")
        base_text = raw_text
    else:
        messages.append("Model output was not valid JSON; building heuristic Stage-1 JSON")
        base_text = raw_text

    data = heuristic_spec_from_text(base_text, diagram_type)
    # If model emitted partial JSON, merge entity names
    if parsed and isinstance(parsed.get("entities"), list):
        for ent in parsed["entities"]:
            if isinstance(ent, dict) and ent.get("name"):
                if not any(e["name"] == ent["name"] for e in data["entities"]):
                    data["entities"].append(
                        {
                            "name": ent["name"],
                            "kind": ent.get("kind") or "class",
                            "attributes": ent.get("attributes") or [],
                            "methods": ent.get("methods") or [],
                        }
                    )
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
