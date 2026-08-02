"""Package-diagram failure taxonomy for thesis evaluation / analytics."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from sqlmodel import Session, select

from app.models import RepairAttempt, RenderAttempt, UMLArtifact


FAILURE_CATEGORIES = (
    "empty_or_incomplete",
    "missing_package_block",
    "unbalanced_braces",
    "self_dependency",
    "invalid_syntax_other",
    "render_engine_error",
    "wrong_diagram_type",
    "unknown",
)


def classify_package_failure(
    plantuml_code: str,
    validation_messages: str | None = None,
    render_errors: list[str] | None = None,
) -> list[str]:
    """Return one or more failure category labels for a package artifact."""
    cats: list[str] = []
    code = plantuml_code or ""
    msgs = (validation_messages or "").lower()
    render_blob = "\n".join(render_errors or []).lower()
    body = re.sub(r"(?is)@startuml|@enduml", "", code).strip()

    if len(body) < 12 or "empty" in msgs or "incomplete" in msgs:
        cats.append("empty_or_incomplete")
    if not re.search(r"(?im)^\s*package\s+", code):
        cats.append("missing_package_block")
    if code.count("{") != code.count("}"):
        cats.append("unbalanced_braces")
    if "self-referential" in msgs or re.search(
        r"(?m)^\s*([A-Za-z_][\w.]*)\s+(\.\.>|->|-->)\s*\1\b", code
    ):
        cats.append("self_dependency")
    if re.search(r"(?m)^\s*class\s+\w+", code) and not re.search(r"(?im)^\s*package\s+", code):
        cats.append("wrong_diagram_type")
    if "error" in render_blob or "syntax" in render_blob or "http 400" in render_blob:
        cats.append("render_engine_error")
    if msgs and not cats:
        cats.append("invalid_syntax_other")
    if not cats:
        cats.append("unknown")
    # stable unique order
    seen: list[str] = []
    for c in cats:
        if c not in seen:
            seen.append(c)
    return seen


def package_failure_report(session: Session) -> dict[str, Any]:
    artifacts = session.exec(
        select(UMLArtifact).where(UMLArtifact.diagram_type == "package")
    ).all()
    failed = [a for a in artifacts if a.render_status != "success"]
    counter: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {c: [] for c in FAILURE_CATEGORIES}

    for a in failed:
        repairs = session.exec(
            select(RepairAttempt).where(RepairAttempt.artifact_id == a.id)
        ).all()
        renders = session.exec(
            select(RenderAttempt).where(RenderAttempt.artifact_id == a.id)
        ).all()
        render_errs = [r.error_output for r in renders if r.error_output]
        render_errs.extend(r.reason for r in repairs if r.reason)
        cats = classify_package_failure(
            a.plantuml_code or "",
            a.validation_messages,
            render_errs,
        )
        for c in cats:
            counter[c] += 1
            if len(examples[c]) < 3:
                examples[c].append(
                    {
                        "id": a.id,
                        "composite_score": a.composite_score,
                        "categories": cats,
                        "plantuml_preview": (a.plantuml_code or "")[:240],
                    }
                )

    return {
        "package_total": len(artifacts),
        "package_failures": len(failed),
        "failure_rate": (len(failed) / len(artifacts)) if artifacts else None,
        "by_category": dict(counter),
        "examples": {k: v for k, v in examples.items() if v},
    }
