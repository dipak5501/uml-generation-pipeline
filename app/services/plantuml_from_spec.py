"""Deterministic, spec-faithful PlantUML generation for professional UML quality."""

from __future__ import annotations

import re
from typing import Any

from app.services.plantuml_validate import sanitize_plantuml_output

_GENERIC_NAME = re.compile(r"^(Module|Entity|Component|Package|Class|Object)\d*$", re.I)
_ARROW = {
    "inheritance": "--|>",
    "generalization": "--|>",
    "extends": "--|>",
    "realization": "..|>",
    "composition": "*--",
    "aggregation": "o--",
    "dependency": "..>",
    "uses": "..>",
    "containment": "+--",
    "contains": "+--",
    "link": "-->",
    "association": "-->",
}


def _safe_id(name: str) -> str:
    text = re.sub(r"[^\w]", "_", (name or "Entity").strip())
    if not text or text[0].isdigit():
        text = "E_" + text
    return text


def _safe_label(text: str, *, max_len: int = 80) -> str:
    """Single-line display text safe to embed in PlantUML (no directive injection)."""
    s = str(text or "")
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # Neutralize preprocessor tokens and diagram delimiters
    s = re.sub(r"(?i)!(?:include|includeurl|import|pragma|define|theme)\b", "", s)
    s = s.replace("@startuml", "").replace("@enduml", "")
    s = s.replace("[", "(").replace("]", ")")
    s = s.replace('"', "'")
    return s[:max_len].strip() or "Item"


def _entity_names(spec: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for ent in spec.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name or _GENERIC_NAME.match(name):
            continue
        if name not in names:
            names.append(name)
    for obj in spec.get("objects") or []:
        if isinstance(obj, dict):
            t = str(obj.get("type") or "").strip()
            if t and t not in names and not _GENERIC_NAME.match(t):
                names.append(t)
    for comp in spec.get("components") or []:
        if isinstance(comp, dict):
            n = str(comp.get("name") or "").strip()
            if n and n not in names and not _GENERIC_NAME.match(n):
                names.append(n)
        elif isinstance(comp, str) and comp not in names:
            names.append(comp)
    for pkg in spec.get("packages") or []:
        if isinstance(pkg, dict):
            for c in pkg.get("contains") or []:
                c = str(c).strip()
                if c and c not in names and not _GENERIC_NAME.match(c):
                    names.append(c)
            n = str(pkg.get("name") or "").strip()
            if n and n not in names and not _GENERIC_NAME.match(n):
                names.append(n)
    return names


def _fmt_members(items: list[Any] | None, prefix: str = "+") -> list[str]:
    lines: list[str] = []
    for item in items or []:
        text = _safe_label(str(item).lstrip("+-#~"), max_len=60)
        if not text or text == "Item":
            continue
        if not text.startswith(("+", "-", "#", "~")):
            text = f"{prefix}{text}"
        lines.append(f"  {text}")
    return lines


def _rel_arrow(rtype: str) -> str:
    return _ARROW.get((rtype or "association").lower().strip(), "-->")


def build_class_plantuml(spec: dict[str, Any]) -> str:
    lines = ["@startuml"]
    summary = _safe_label(str(spec.get("summary") or ""), max_len=80)
    if summary and summary != "Item":
        lines.append(f"title {summary}")
    entities = [e for e in (spec.get("entities") or []) if isinstance(e, dict) and e.get("name")]
    if not entities:
        for name in _entity_names(spec):
            entities.append({"name": name, "attributes": [], "methods": []})
    # Honest empty class model — never invent types from script variables
    if not entities or spec.get("script_without_types"):
        lines.append("title No class declarations found in source")
        lines.append("note as NoTypes")
        lines.append("  This source is a script/driver with no `class` / interface types.")
        lines.append("  Configuration variables and string paths are NOT UML classes.")
        lines.append("  Paste domain model classes (class/interface types) to build a class diagram.")
        lines.append("end note")
        lines.append("@enduml")
        return "\n".join(lines) + "\n"
    for ent in entities[:12]:
        name = _safe_id(str(ent["name"]))
        body = _fmt_members(ent.get("attributes")) + _fmt_members(ent.get("methods"))
        if body:
            lines.append(f"class {name} {{")
            lines.extend(body)
            lines.append("}")
        else:
            lines.append(f"class {name}")
    for rel in spec.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        src, tgt = rel.get("source"), rel.get("target")
        if not src or not tgt:
            continue
        arrow = _rel_arrow(str(rel.get("type") or "association"))
        label = str(rel.get("label") or "").strip()
        # Prefer child --|> parent for inheritance wording
        if arrow == "--|>":
            line = f"{_safe_id(str(src))} --|> {_safe_id(str(tgt))}"
        elif arrow in {"-->", "..>", "*--", "o--", "+--"}:
            # Do not also draw a generic association when inheritance/containment exists
            already = any(
                isinstance(r2, dict)
                and str(r2.get("source")) == src
                and str(r2.get("target")) == tgt
                and _rel_arrow(str(r2.get("type") or "")) == "--|>"
                for r2 in (spec.get("relationships") or [])
            )
            if already:
                continue
            line = f"{_safe_id(str(src))} {arrow} {_safe_id(str(tgt))}"
        else:
            line = f"{_safe_id(str(src))} {arrow} {_safe_id(str(tgt))}"
        if label:
            line += f" : {_safe_label(label, max_len=40)}"
        lines.append(line)
    if len(entities) >= 2 and not any(isinstance(r, dict) and r.get("source") for r in (spec.get("relationships") or [])):
        lines.append(f"{_safe_id(entities[0]['name'])} --> {_safe_id(entities[1]['name'])}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def build_object_plantuml(spec: dict[str, Any]) -> str:
    lines = ["@startuml"]
    objects = [o for o in (spec.get("objects") or []) if isinstance(o, dict)]
    if not objects:
        for name in _entity_names(spec)[:4]:
            objects.append({"name": name[:1].lower() + name[1:] + "1", "type": name})
    aliases: list[str] = []
    for obj in objects[:8]:
        typ = _safe_id(str(obj.get("type") or obj.get("name") or "Object"))
        raw_name = str(obj.get("name") or (typ[:1].lower() + typ[1:] + "1"))
        alias = _safe_id(raw_name)
        aliases.append(alias)
        vals = obj.get("values") or obj.get("attributes") or []
        # Prefer canonical PlantUML: object alias : Type
        if vals:
            lines.append(f"object {alias} : {typ} {{")
            for v in vals[:6]:
                lines.append(f"  {_safe_label(v, max_len=40)}")
            lines.append("}")
        else:
            lines.append(f"object {alias} : {typ}")
    for rel in spec.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        src, tgt = rel.get("source"), rel.get("target")
        if not src or not tgt:
            continue

        def _alias_for(token: str) -> str | None:
            t = token.lower()
            for a in aliases:
                if a.lower() == t or a.lower().startswith(t[:3]):
                    return a
            for obj in objects:
                if str(obj.get("type") or "").lower() == t:
                    return _safe_id(str(obj.get("name")))
            return _safe_id(token)

        s, t = _alias_for(str(src)), _alias_for(str(tgt))
        if s and t and s != t:
            label = _safe_label(str(rel.get("label") or "link"), max_len=40) or "link"
            lines.append(f"{s} --> {t} : {label}")
    if len(aliases) >= 2 and not any("-->" in ln for ln in lines):
        lines.append(f"{aliases[0]} --> {aliases[1]} : link")
        if len(aliases) >= 3:
            lines.append(f"{aliases[0]} --> {aliases[2]} : link")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def build_component_plantuml(spec: dict[str, Any]) -> str:
    lines = ["@startuml"]
    comps: list[dict[str, Any]] = []
    for c in spec.get("components") or []:
        if isinstance(c, dict) and c.get("name"):
            comps.append(c)
        elif isinstance(c, str) and c.strip():
            comps.append({"name": c.strip()})
    if not comps:
        for name in _entity_names(spec):
            comps.append({"name": name})
    filtered = [
        c
        for c in comps
        if c.get("name")
        and not _GENERIC_NAME.match(str(c["name"]))
        and str(c["name"]).lower() not in {"svc", "api", "store", "service"}
    ]
    # Never emit an empty component diagram — keep original names if the filter wiped them.
    comps = (filtered or [c for c in comps if c.get("name")] or [{"name": "Application"}, {"name": "DomainService"}])[:8]
    aliases: dict[str, str] = {}
    for c in comps:
        name = str(c["name"]).strip()
        alias = _safe_id(name)
        aliases[name] = alias
        display = _safe_label(name, max_len=48)
        lines.append(f'[{display}] as {alias}')
        # Only emit interfaces when the specification actually names them
        ifaces = c.get("interfaces") if isinstance(c.get("interfaces"), list) else []
        for iface in ifaces[:3]:
            iface_name = _safe_label(str(iface), max_len=40)
            if not iface_name or iface_name == "Item":
                continue
            iface_alias = _safe_id(iface_name)
            lines.append(f'() "{iface_name}" as {iface_alias}')
            lines.append(f"{alias} --> {iface_alias}")
    # dependencies from relationships
    for rel in spec.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        src, tgt = str(rel.get("source") or ""), str(rel.get("target") or "")
        if not src or not tgt:
            continue
        sa = next((aliases[k] for k in aliases if k.lower() == src.lower() or src.lower() in k.lower()), None)
        ta = next((aliases[k] for k in aliases if k.lower() == tgt.lower() or tgt.lower() in k.lower()), None)
        if sa and ta and sa != ta:
            label = _safe_label(str(rel.get("label") or "uses"), max_len=40) or "uses"
            lines.append(f"{sa} ..> {ta} : {label}")
    if len(comps) >= 2 and not any("..>" in ln for ln in lines):
        names = list(aliases.keys())
        lines.append(f"{aliases[names[0]]} ..> {aliases[names[1]]} : uses")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def build_package_plantuml(spec: dict[str, Any]) -> str:
    lines = ["@startuml"]
    packages = [p for p in (spec.get("packages") or []) if isinstance(p, dict) and p.get("name")]
    names = _entity_names(spec)
    if not packages:
        # Named packages from domain entities (not generic domain/application)
        if len(names) >= 3:
            packages = [{"name": n, "contains": [n]} for n in names[:6]]
        elif names:
            packages = [{"name": names[0], "contains": names}]
        else:
            packages = [{"name": "Core", "contains": ["Entity"]}]

    # If many peer packages share no hierarchy, nest them under a single system shell
    # so the diagram shows containment rather than a flat list of same-level peers.
    nest_under_system = (
        len(packages) >= 3
        and all("." not in str(p["name"]) for p in packages)
        and not any(p.get("parent") for p in packages)
    )

    pkg_ids: list[str] = []
    if nest_under_system:
        lines.append("package System {")
    for pkg in packages[:8]:
        pname = _safe_id(str(pkg["name"]))
        pkg_ids.append(pname)
        indent = "  " if nest_under_system else ""
        lines.append(f"{indent}package {pname} {{")
        contains = [str(x) for x in (pkg.get("contains") or []) if str(x).strip()]
        if not contains:
            contains = [str(pkg["name"])]
        wrote = False
        for item in contains[:8]:
            if _GENERIC_NAME.match(item):
                continue
            lines.append(f"{indent}  class {_safe_id(item)}")
            wrote = True
        if not wrote:
            lines.append(f"{indent}  class {pname}")
        lines.append(f"{indent}}}")
    if nest_under_system:
        lines.append("}")
    # package-level dependencies from relationships / sequential
    rels_added = 0
    for rel in spec.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        src, tgt = str(rel.get("source") or ""), str(rel.get("target") or "")
        if not src or not tgt:
            continue
        sa = next((p for p in pkg_ids if p.lower() == _safe_id(src).lower() or src.lower() in p.lower()), None)
        ta = next((p for p in pkg_ids if p.lower() == _safe_id(tgt).lower() or tgt.lower() in p.lower()), None)
        if sa and ta and sa != ta:
            label = _safe_label(str(rel.get("label") or "depends"), max_len=40) or "depends"
            lines.append(f"{sa} ..> {ta} : {label}")
            rels_added += 1
    if rels_added == 0 and len(pkg_ids) >= 2:
        for i in range(len(pkg_ids) - 1):
            lines.append(f"{pkg_ids[i]} ..> {pkg_ids[i+1]} : depends")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def build_flowchart_plantuml(spec: dict[str, Any]) -> str:
    steps = spec.get("process_steps") or spec.get("steps") or []
    clean: list[str] = []
    for s in steps:
        if isinstance(s, dict):
            clean.append(_safe_label(str(s.get("name") or s.get("action") or s), max_len=60))
        else:
            clean.append(_safe_label(str(s), max_len=60))
    clean = [c for c in clean if c and c != "Item"][:12]
    if len(clean) < 2:
        names = _entity_names(spec)
        clean = [f"Start {names[0]}" if names else "Start", "Process", "Complete"]
    lines = ["@startuml", "start"]
    mid = len(clean) // 2
    for i, step in enumerate(clean):
        step = step.rstrip(";")
        if i == mid and len(clean) >= 3:
            lines.append(f"if ({step}?) then (yes)")
        else:
            lines.append(f":{step};")
    if any(ln.startswith("if (") for ln in lines):
        lines.append("else (no)")
        lines.append(":Handle alternate path;")
        lines.append("endif")
    lines.append("stop")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def plantuml_from_spec(spec: dict[str, Any], diagram_type: str | None = None) -> str:
    dtype = (diagram_type or spec.get("diagram_type") or "class").lower().strip()
    if dtype == "object":
        code = build_object_plantuml(spec)
    elif dtype == "component":
        code = build_component_plantuml(spec)
    elif dtype == "package":
        code = build_package_plantuml(spec)
    elif dtype == "flowchart":
        code = build_flowchart_plantuml(spec)
    else:
        code = build_class_plantuml(spec)
    return sanitize_plantuml_output(code, diagram_type=dtype)


def fidelity_report(code: str, spec: dict[str, Any], diagram_type: str) -> dict[str, Any]:
    """Score how well PlantUML covers Stage-1 required names and relationships."""
    required = _entity_names(spec)
    if diagram_type == "package":
        for p in spec.get("packages") or []:
            if isinstance(p, dict) and p.get("name"):
                n = str(p["name"])
                if n not in required and not _GENERIC_NAME.match(n):
                    required.append(n)
    if diagram_type == "component":
        for c in spec.get("components") or []:
            if isinstance(c, dict) and c.get("name"):
                n = str(c["name"])
                if n not in required and not _GENERIC_NAME.match(n):
                    required.append(n)
    code_l = code.lower()
    found = []
    missing = []
    for name in required:
        stem = re.sub(r"(service|api|store|repository|module|package)s?$", "", name.lower())
        ok = bool(re.search(rf"\b{re.escape(name.lower())}\b", code_l)) or (
            len(stem) >= 4 and stem in code_l
        )
        (found if ok else missing).append(name)
    generic_hits = re.findall(r"\bModule\d+\b", code, flags=re.I)
    generic_hits += re.findall(r"\bEntity[AB]\b", code, flags=re.I)
    # Relationship coverage: pairs should appear together on a connector line
    rel_total = 0
    rel_hits = 0
    rel_missing: list[str] = []
    for rel in spec.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        src, tgt = str(rel.get("source") or ""), str(rel.get("target") or "")
        if not src or not tgt:
            continue
        rel_total += 1
        hit = False
        for line in code.splitlines():
            low = line.lower()
            if src.lower() in low and tgt.lower() in low and re.search(
                r"(-->|\.\.>|\*--|o--|\-\-\|>|<\|--|..\|>|\+\-\-)", line
            ):
                hit = True
                break
        if hit:
            rel_hits += 1
        else:
            rel_missing.append(f"{src}-{tgt}")
    recall = len(found) / max(1, len(required)) if required else 1.0
    rel_recall = 1.0 if rel_total == 0 else rel_hits / rel_total
    ok = (
        recall >= 0.75
        and not generic_hits
        and len(missing) <= max(1, len(required) // 4)
        and rel_recall >= 0.5
    )
    return {
        "ok": ok,
        "recall": recall,
        "rel_recall": rel_recall,
        "required": required,
        "found": found,
        "missing": missing,
        "rel_missing": rel_missing,
        "generic_placeholders": generic_hits,
    }


def ensure_faithful_plantuml(
    code: str,
    spec: dict[str, Any],
    diagram_type: str,
    *,
    min_recall: float = 0.75,
) -> tuple[str, dict[str, Any]]:
    """
    Keep LLM PlantUML only if it faithfully covers the Stage-1 spec.
    Otherwise replace with deterministic diagram from the spec.
    """
    # Scripts without types: always use grounded builder (never keep fake classes)
    if spec.get("script_without_types"):
        deterministic = plantuml_from_spec(spec, diagram_type)
        return deterministic, {
            "ok": True,
            "recall": 1.0,
            "source": "spec-builder",
            "replaced": True,
            "reason": "script_without_types",
        }
    report = fidelity_report(code, spec, diagram_type)
    if report["ok"] and report["recall"] >= min_recall:
        return sanitize_plantuml_output(code, diagram_type=diagram_type), {**report, "source": "model"}
    deterministic = plantuml_from_spec(spec, diagram_type)
    report2 = fidelity_report(deterministic, spec, diagram_type)
    return deterministic, {**report2, "source": "spec-builder", "replaced": True, "prior": report}
