"""Multi-layer UML acceptance: syntax → compile → render → structure → semantics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.services.plantuml_from_spec import fidelity_report
from app.services.plantuml_validate import ValidationResult, validate_basic_syntax
from app.services.traceability import evaluate_semantics
from app.services.uml_structure import validate_uml_structure
from app.settings import get_settings
from uml_pipeline.render import check_plantuml_syntax


FAILURE_SYNTAX = "syntax"
FAILURE_COMPILE = "compile"
FAILURE_RENDER = "render"
FAILURE_STRUCTURE = "uml_structure"
FAILURE_MISSING = "missing_element"
FAILURE_RELATIONSHIP = "wrong_relationship"
FAILURE_HALLUCINATION = "hallucinated_entity"
FAILURE_PACKAGE = "package_hierarchy"
FAILURE_SEMANTIC = "semantic_alignment"


@dataclass
class GateResult:
    name: str
    ok: bool
    messages: list[str] = field(default_factory=list)


@dataclass
class AcceptanceReport:
    accepted: bool
    generated: bool
    syntax_ok: bool
    compile_ok: bool | None
    render_ok: bool
    uml_rules_ok: bool
    consistency_ok: bool
    semantic_ok: bool
    failure_category: str | None
    gates: list[GateResult] = field(default_factory=list)
    semantic: dict[str, Any] = field(default_factory=dict)
    fidelity: dict[str, Any] = field(default_factory=dict)
    repair_iterations: int = 0

    def summary_lines(self) -> list[str]:
        lines = [
            f"ACCEPT generated={self.generated} syntax={self.syntax_ok} "
            f"compile={self.compile_ok} render={self.render_ok} "
            f"uml_rules={self.uml_rules_ok} consistency={self.consistency_ok} "
            f"semantic={self.semantic_ok} accepted={self.accepted}"
        ]
        if self.failure_category:
            lines.append(f"failure_category={self.failure_category}")
        for g in self.gates:
            if not g.ok and g.messages:
                lines.append(f"{g.name}: " + "; ".join(g.messages[:4]))
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "generated": self.generated,
            "syntax_ok": self.syntax_ok,
            "compile_ok": self.compile_ok,
            "render_ok": self.render_ok,
            "uml_rules_ok": self.uml_rules_ok,
            "consistency_ok": self.consistency_ok,
            "semantic_ok": self.semantic_ok,
            "failure_category": self.failure_category,
            "repair_iterations": self.repair_iterations,
            "gates": [asdict(g) for g in self.gates],
            "semantic": self.semantic,
            "fidelity": self.fidelity,
        }


def classify_failure(report: AcceptanceReport) -> str | None:
    if report.accepted:
        return None
    if not report.generated:
        return FAILURE_SYNTAX
    if not report.syntax_ok:
        return FAILURE_SYNTAX
    if report.compile_ok is False:
        return FAILURE_COMPILE
    if not report.render_ok:
        return FAILURE_RENDER
    if not report.uml_rules_ok:
        dtype_msgs = " ".join(m for g in report.gates if g.name == "uml_rules" for m in g.messages)
        if "package" in dtype_msgs.lower() or "containment" in dtype_msgs.lower():
            return FAILURE_PACKAGE
        return FAILURE_STRUCTURE
    sem = report.semantic or {}
    if sem.get("missing") and not sem.get("completeness_ok", True):
        return FAILURE_MISSING
    if sem.get("extra") and not sem.get("hallucination_ok", True):
        return FAILURE_HALLUCINATION
    if report.fidelity.get("rel_missing") and not report.consistency_ok:
        return FAILURE_RELATIONSHIP
    if not report.semantic_ok or not report.consistency_ok:
        return FAILURE_SEMANTIC
    return FAILURE_SEMANTIC


def evaluate_acceptance(
    *,
    requirement: str,
    plantuml: str,
    diagram_type: str,
    spec: dict[str, Any] | None = None,
    render_ok: bool = False,
    repair_iterations: int = 0,
    run_compile: bool = True,
) -> AcceptanceReport:
    gates: list[GateResult] = []
    generated = bool((plantuml or "").strip()) and "@startuml" in (plantuml or "").lower()
    gates.append(GateResult("generated", generated, [] if generated else ["No PlantUML generated"]))

    syntax = (
        validate_basic_syntax(plantuml or "")
        if generated
        else ValidationResult(False, ["empty"])
    )
    gates.append(GateResult("syntax", syntax.ok, syntax.messages))

    compile_ok: bool | None = None
    compile_msgs: list[str] = []
    if generated and run_compile:
        settings = get_settings()
        ok, err = check_plantuml_syntax(plantuml, settings.plantuml_jar)
        compile_ok = ok
        if err:
            compile_msgs.append(err)
    gates.append(
        GateResult(
            "compile",
            compile_ok is not False,
            compile_msgs if compile_ok is False else [],
        )
    )

    gates.append(GateResult("render", render_ok, [] if render_ok else ["Render gate failed"]))

    structure = (
        validate_uml_structure(plantuml or "", diagram_type)
        if generated
        else ValidationResult(False, ["empty"])
    )
    gates.append(GateResult("uml_rules", structure.ok, structure.messages))

    fid: dict[str, Any] = {}
    consistency_ok = True
    if spec and generated:
        fid = fidelity_report(plantuml, spec, diagram_type)
        consistency_ok = bool(fid.get("ok")) or float(fid.get("recall") or 0) >= 0.6
    gates.append(
        GateResult(
            "consistency",
            consistency_ok,
            []
            if consistency_ok
            else [f"Spec coverage weak (recall={fid.get('recall')}, missing={fid.get('missing')})"],
        )
    )

    sem = evaluate_semantics(
        requirement=requirement,
        plantuml=plantuml or "",
        diagram_type=diagram_type,
        spec=spec,
    )
    gates.append(GateResult("semantic", sem.ok, sem.messages))

    syntax_ok = syntax.ok
    uml_ok = structure.ok
    semantic_ok = sem.ok
    accepted = (
        generated
        and syntax_ok
        and compile_ok is not False
        and render_ok
        and uml_ok
        and consistency_ok
        and semantic_ok
    )
    report = AcceptanceReport(
        accepted=accepted,
        generated=generated,
        syntax_ok=syntax_ok,
        compile_ok=compile_ok,
        render_ok=render_ok,
        uml_rules_ok=uml_ok,
        consistency_ok=consistency_ok,
        semantic_ok=semantic_ok,
        failure_category=None,
        gates=gates,
        semantic={
            "completeness_ok": sem.completeness_ok,
            "correctness_ok": sem.correctness_ok,
            "hallucination_ok": sem.hallucination_ok,
            "contradiction_ok": sem.contradiction_ok,
            "traceability_ok": sem.traceability_ok,
            "required": sem.required,
            "found": sem.found,
            "missing": sem.missing,
            "extra": sem.extra,
            "traces": sem.traces,
            "recall": sem.recall,
        },
        fidelity=fid,
        repair_iterations=repair_iterations,
    )
    report.failure_category = classify_failure(report)
    return report


def write_acceptance_sidecar(artifact_dir: Path, report: AcceptanceReport) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "acceptance.json"
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path
