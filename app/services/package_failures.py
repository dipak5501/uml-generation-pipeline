"""Package-diagram failure taxonomy for thesis evaluation / analytics (RQ3)."""

from __future__ import annotations

import math
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


def _mean(xs: list[float]) -> float | None:
    return (sum(xs) / len(xs)) if xs else None


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """95% Wilson score interval for a proportion."""
    if n <= 0:
        return None, None
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def package_failure_report(session: Session) -> dict[str, Any]:
    """Live Mac Studio package taxonomy + repair win-rate for RQ3."""
    artifacts = session.exec(
        select(UMLArtifact).where(UMLArtifact.diagram_type == "package")
    ).all()
    failed = [a for a in artifacts if a.render_status != "success"]
    succeeded = [a for a in artifacts if a.render_status == "success"]
    counter: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {c: [] for c in FAILURE_CATEGORIES}

    repair_attempts = 0
    repair_successes = 0
    artifacts_with_repair = 0
    rescued = 0  # had ≥1 repair and final render success

    for a in artifacts:
        repairs = session.exec(
            select(RepairAttempt).where(RepairAttempt.artifact_id == a.id)
        ).all()
        if repairs:
            artifacts_with_repair += 1
            repair_attempts += len(repairs)
            repair_successes += sum(1 for r in repairs if r.success)
            if a.render_status == "success":
                rescued += 1

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

    n_pkg = len(artifacts)
    n_fail = len(failed)
    n_ok = len(succeeded)
    by_category_rates = {
        cat: {
            "count": counter.get(cat, 0),
            "share_of_failures": (counter[cat] / n_fail) if n_fail else None,
            "share_of_packages": (counter[cat] / n_pkg) if n_pkg else None,
        }
        for cat in FAILURE_CATEGORIES
        if counter.get(cat, 0)
    }
    # also include any unexpected keys
    for cat, count in counter.items():
        if cat not in by_category_rates:
            by_category_rates[cat] = {
                "count": count,
                "share_of_failures": (count / n_fail) if n_fail else None,
                "share_of_packages": (count / n_pkg) if n_pkg else None,
            }

    fail_lo, fail_hi = _wilson_ci(n_fail, n_pkg)
    attempt_win = (repair_successes / repair_attempts) if repair_attempts else None
    rescue_rate = (rescued / artifacts_with_repair) if artifacts_with_repair else None

    return {
        "claim_scope": "live_mac_studio",
        "note": (
            "Live package taxonomy on this Mac Studio database — not the paper "
            "DeepSeek-32B n=8,000 run. Do not cite these rates as paper RQ3 numbers."
        ),
        "package_total": n_pkg,
        "package_successes": n_ok,
        "package_failures": n_fail,
        "failure_rate": (n_fail / n_pkg) if n_pkg else None,
        "failure_rate_ci95": {"low": fail_lo, "high": fail_hi},
        "success_rate": (n_ok / n_pkg) if n_pkg else None,
        "mean_s_success": _mean([a.composite_score for a in succeeded]),
        "mean_s_failure": _mean([a.composite_score for a in failed]),
        "majority_accept_success_pct": (
            100.0 * sum(1 for a in succeeded if a.majority_accepted) / n_ok if n_ok else None
        ),
        "by_category": dict(counter),
        "by_category_rates": by_category_rates,
        "repair": {
            "artifacts_with_repair": artifacts_with_repair,
            "repair_attempts": repair_attempts,
            "repair_successes": repair_successes,
            "attempt_win_rate": attempt_win,
            "rescued_artifacts": rescued,
            "rescue_rate": rescue_rate,
        },
        "examples": {k: v for k, v in examples.items() if v},
    }


def format_package_failure_chapter(report: dict[str, Any]) -> str:
    """Markdown RQ3 chapter from a package_failure_report dict."""
    lines: list[str] = [
        "# RQ3 · Package Failure Chapter (Live Mac Studio)",
        "",
        "> **Claim scope:** live Mac Studio LoRA stack only. "
        "Paper DeepSeek-32B package render success (81.1%) is a separate experiment.",
        "",
        report.get("note") or "",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Package artifacts | {report.get('package_total', 0)} |",
        f"| Render successes | {report.get('package_successes', 0)} |",
        f"| Render failures | {report.get('package_failures', 0)} |",
    ]
    fr = report.get("failure_rate")
    ci = report.get("failure_rate_ci95") or {}
    if fr is not None:
        ci_s = ""
        if ci.get("low") is not None and ci.get("high") is not None:
            ci_s = f" (95% Wilson CI [{ci['low']:.1%}, {ci['high']:.1%}])"
        lines.append(f"| Failure rate | {fr:.1%}{ci_s} |")
    if report.get("mean_s_success") is not None:
        lines.append(f"| Mean S (success) | {report['mean_s_success']:.2f} |")
    if report.get("mean_s_failure") is not None:
        lines.append(f"| Mean S (failure) | {report['mean_s_failure']:.2f} |")
    maj = report.get("majority_accept_success_pct")
    if maj is not None:
        lines.append(f"| Majority A among successes | {maj:.1f}% |")

    repair = report.get("repair") or {}
    lines.extend(
        [
            "",
            "## Repair win-rate (package only)",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Artifacts that attempted repair | {repair.get('artifacts_with_repair', 0)} |",
            f"| Repair attempts | {repair.get('repair_attempts', 0)} |",
            f"| Successful repair attempts | {repair.get('repair_successes', 0)} |",
        ]
    )
    if repair.get("attempt_win_rate") is not None:
        lines.append(f"| Attempt win-rate | {repair['attempt_win_rate']:.1%} |")
    lines.append(f"| Rescued to final render success | {repair.get('rescued_artifacts', 0)} |")
    if repair.get("rescue_rate") is not None:
        lines.append(f"| Rescue rate (among repaired) | {repair['rescue_rate']:.1%} |")

    lines.extend(["", "## Failure taxonomy", "", "| Category | Count | Share of failures | Share of packages |", "|----------|------:|------------------:|------------------:|"])
    rates = report.get("by_category_rates") or {}
    for cat, row in sorted(rates.items(), key=lambda kv: -kv[1].get("count", 0)):
        sof = row.get("share_of_failures")
        sop = row.get("share_of_packages")
        lines.append(
            f"| `{cat}` | {row.get('count', 0)} | "
            f"{sof:.1%} | {sop:.1%} |"
            if sof is not None and sop is not None
            else f"| `{cat}` | {row.get('count', 0)} | — | — |"
        )

    lines.extend(
        [
            "",
            "## Interpretation (for defense)",
            "",
            "1. Package diagrams remain the hardest of the four design-phase types on this server, "
            "matching the paper ordering class > object > component > package.",
            "2. Taxonomy labels isolate stage-boundary failures (syntax / containment / render engine) "
            "so RQ3 is not only a score gap but a failure-mode story.",
            "3. Repair win-rate shows whether the verification→repair loop recovers package failures; "
            "cite attempt win-rate and rescue rate separately.",
            "",
            "## Examples",
            "",
        ]
    )
    examples = report.get("examples") or {}
    if not examples:
        lines.append("_No failed package diagrams stored yet._")
    else:
        for cat, rows in examples.items():
            lines.append(f"### `{cat}`")
            lines.append("")
            for row in rows:
                lines.append(
                    f"- Artifact #{row.get('id')} · S={row.get('composite_score')} · "
                    f"categories={row.get('categories')}"
                )
                preview = (row.get("plantuml_preview") or "").strip()
                if preview:
                    lines.append("")
                    lines.append("```")
                    lines.append(preview)
                    lines.append("```")
                lines.append("")

    lines.append("")
    lines.append("Regenerate: `python scripts/generate_rq3_package_chapter.py`")
    lines.append("")
    return "\n".join(lines)
