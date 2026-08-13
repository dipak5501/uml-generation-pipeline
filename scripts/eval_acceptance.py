#!/usr/bin/env python3
"""Run the multi-layer UML acceptance pipeline on the benchmark requirements.

Produces a measured scoreboard. Does not claim success without numbers.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.acceptance import evaluate_acceptance, write_acceptance_sidecar
from app.services.plantuml_from_spec import plantuml_from_spec
from app.services.plantuml_validate import validate_diagram
from app.services.repair import repair_plantuml
from app.services.spec_json import ensure_valid_spec
from app.settings import Settings, get_settings
from uml_pipeline.render import check_plantuml_syntax, render_plantuml

REQ_FILE = ROOT / "sample_data" / "requirements.txt"
GOLDEN_FILE = ROOT / "tests" / "golden" / "cases.json"
OUT_DIR = ROOT / "data" / "acceptance_eval"
REPORT_JSON = ROOT / "reports" / "acceptance_eval.json"
REPORT_MD = ROOT / "reports" / "acceptance_eval.md"
DIAGRAM_TYPES = ("class", "object", "component", "package")
MAX_REPAIR = 3

# Validator true-negative controls: these MUST be rejected.
NEGATIVE_CASES = [
    {
        "id": "NEG-empty",
        "requirement": "Library system with Book and Member.",
        "diagram_type": "class",
        "plantuml": "@startuml\n@enduml\n",
        "render_ok": False,
    },
    {
        "id": "NEG-missing",
        "requirement": "Library management system with classes Book, Member, Loan, and Librarian.",
        "diagram_type": "class",
        "plantuml": "@startuml\nclass Widget\nclass Gadget\nWidget --> Gadget\n@enduml\n",
        "render_ok": True,
    },
    {
        "id": "NEG-hallucination",
        "requirement": "Library system with Book and Member.",
        "diagram_type": "class",
        "plantuml": (
            "@startuml\nclass Book\nclass Member\nclass UnicornLauncher\n"
            "class QuantumRouter\nclass DragonService\nBook --> Member\n@enduml\n"
        ),
        "render_ok": True,
    },
    {
        "id": "NEG-syntax",
        "requirement": "Banking with Account and Ledger.",
        "diagram_type": "package",
        "plantuml": "@startuml\npackage Core {\nclass Account\n@enduml\n",
        "render_ok": False,
    },
    {
        "id": "NEG-sequence-unsupported",
        "requirement": "User logs in then views dashboard.",
        "diagram_type": "sequence",
        "plantuml": "@startuml\nAlice -> Bob: login\n@enduml\n",
        "render_ok": True,
    },
]


def load_requirements() -> list[tuple[str, str]]:
    lines = [
        ln.strip()
        for ln in REQ_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    return [(f"REQ-{i:03d}", text) for i, text in enumerate(lines, start=1)]


def generate_and_accept(
    req_id: str,
    requirement: str,
    diagram_type: str,
    settings: Settings,
    case_dir: Path,
) -> dict:
    t0 = time.time()
    spec, _, _ = ensure_valid_spec(requirement, diagram_type, source_text=requirement)
    plantuml = plantuml_from_spec(spec, diagram_type)
    retries = 0
    last_category = None
    compile_ok = None
    compile_err = None
    render_ok = False
    render_err = None
    image_path = None

    while True:
        v = validate_diagram(plantuml, diagram_type)
        compile_ok, compile_err = check_plantuml_syntax(
            plantuml, settings.plantuml_jar, work_dir=case_dir / "syntax"
        )
        img, render_err = render_plantuml(
            plantuml, case_dir, settings.plantuml_jar, fmt=settings.image_format
        )
        render_ok = img is not None
        if img is not None:
            image_path = str(img)

        report = evaluate_acceptance(
            requirement=requirement,
            plantuml=plantuml,
            diagram_type=diagram_type,
            spec=spec,
            render_ok=render_ok,
            repair_iterations=retries,
        )
        if report.accepted or retries >= MAX_REPAIR:
            break
        last_category = report.failure_category
        errors = []
        if not v.ok:
            errors.extend(v.messages)
        if compile_ok is False and compile_err:
            errors.append(compile_err)
        if not render_ok:
            errors.append(render_err or "render failed")
        for g in report.gates:
            if not g.ok:
                errors.extend(g.messages)
        repaired = repair_plantuml(
            plantuml,
            requirement,
            diagram_type,
            errors or [last_category or "unknown"],
            settings=settings,
            category=last_category or "syntax",
            spec_json=spec,
        )
        plantuml = repaired.code
        retries += 1

    write_acceptance_sidecar(case_dir, report)
    (case_dir / "diagram.puml").write_text(plantuml, encoding="utf-8")
    (case_dir / "requirement.txt").write_text(requirement, encoding="utf-8")

    return {
        "requirement_id": req_id,
        "diagram_type": diagram_type,
        "requirement": requirement,
        "expected_concepts": report.semantic.get("required") or [],
        "generated_plantuml": plantuml,
        "rendered_diagram": image_path,
        "generated": report.generated,
        "syntax_ok": report.syntax_ok,
        "compile_ok": report.compile_ok,
        "render_ok": report.render_ok,
        "uml_rules_ok": report.uml_rules_ok,
        "consistency_ok": report.consistency_ok,
        "semantic_ok": report.semantic_ok,
        "accepted": report.accepted,
        "failure_category": report.failure_category,
        "retry_count": retries,
        "elapsed_sec": round(time.time() - t0, 3),
        "semantic": report.semantic,
        "fidelity": report.fidelity,
        "messages": [m for g in report.gates if not g.ok for m in g.messages],
    }


def summarize(rows: list[dict], label: str) -> dict:
    n = len(rows) or 1
    fails = [r for r in rows if not r["accepted"]]
    cats = Counter(r["failure_category"] for r in fails if r.get("failure_category"))
    return {
        "label": label,
        "total": len(rows),
        "generated_successfully": sum(1 for r in rows if r["generated"]),
        "plantuml_compiled": sum(1 for r in rows if r["compile_ok"] is not False),
        "syntax_valid": sum(1 for r in rows if r["syntax_ok"]),
        "rendered": sum(1 for r in rows if r["render_ok"]),
        "uml_rule_pass": sum(1 for r in rows if r["uml_rules_ok"]),
        "semantic_aligned": sum(1 for r in rows if r["semantic_ok"]),
        "full_pipeline_accepted": sum(1 for r in rows if r["accepted"]),
        "average_repair_iterations": round(sum(r["retry_count"] for r in rows) / n, 3),
        "failure_distribution": dict(cats),
        "remaining_failures": len(fails),
        "rates": {
            "generation_success_rate": round(sum(1 for r in rows if r["generated"]) / n, 4),
            "syntax_validity_rate": round(sum(1 for r in rows if r["syntax_ok"]) / n, 4),
            "rendering_success_rate": round(sum(1 for r in rows if r["render_ok"]) / n, 4),
            "uml_rule_pass_rate": round(sum(1 for r in rows if r["uml_rules_ok"]) / n, 4),
            "semantic_alignment_rate": round(sum(1 for r in rows if r["semantic_ok"]) / n, 4),
            "end_to_end_acceptance_rate": round(sum(1 for r in rows if r["accepted"]) / n, 4),
        },
    }


def fmt_scoreboard(s: dict) -> str:
    t = s["total"]
    lines = [
        f"{s['label']}",
        f"Total test cases: {t}",
        f"Generated successfully: {s['generated_successfully']}/{t}",
        f"PlantUML compiled: {s['plantuml_compiled']}/{t}",
        f"Syntax valid: {s['syntax_valid']}/{t}",
        f"Rendered: {s['rendered']}/{t}",
        f"UML rule validation: {s['uml_rule_pass']}/{t}",
        f"Semantic validation: {s['semantic_aligned']}/{t}",
        f"Full pipeline accepted: {s['full_pipeline_accepted']}/{t}",
        f"Average repair iterations: {s['average_repair_iterations']}",
        f"Remaining failures: {s['remaining_failures']}",
    ]
    if s["failure_distribution"]:
        lines.append("Failure distribution: " + ", ".join(f"{k}={v}" for k, v in s["failure_distribution"].items()))
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="UML multi-layer acceptance evaluation")
    parser.add_argument(
        "--reuse-benchmark",
        action="store_true",
        help="Reuse previously saved REQ-* benchmark rows from reports/acceptance_eval.json",
    )
    args = parser.parse_args()

    settings = get_settings()
    settings = settings.model_copy(update={"mock_providers": True})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    golden_rows: list[dict] = []
    for case in json.loads(GOLDEN_FILE.read_text(encoding="utf-8")):
        case_dir = OUT_DIR / "golden" / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        golden_rows.append(
            generate_and_accept(case["id"], case["requirement"], case["diagram_type"], settings, case_dir)
        )

    negative_rows: list[dict] = []
    for case in NEGATIVE_CASES:
        report = evaluate_acceptance(
            requirement=case["requirement"],
            plantuml=case["plantuml"],
            diagram_type=case["diagram_type"],
            spec=None,
            render_ok=case["render_ok"],
            run_compile=False,
        )
        correctly_rejected = not report.accepted
        negative_rows.append(
            {
                "requirement_id": case["id"],
                "diagram_type": case["diagram_type"],
                "requirement": case["requirement"],
                "generated": report.generated,
                "syntax_ok": report.syntax_ok,
                "compile_ok": report.compile_ok,
                "render_ok": report.render_ok,
                "uml_rules_ok": report.uml_rules_ok,
                "consistency_ok": report.consistency_ok,
                "semantic_ok": report.semantic_ok,
                "accepted": report.accepted,
                "correctly_rejected": correctly_rejected,
                "failure_category": report.failure_category,
                "retry_count": 0,
                "messages": [m for g in report.gates if not g.ok for m in g.messages],
            }
        )
        print(
            f"  {case['id']}: rejected={correctly_rejected} category={report.failure_category}",
            flush=True,
        )

    bench_rows: list[dict] = []
    if args.reuse_benchmark and REPORT_JSON.is_file():
        prior = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        bench_rows = [
            c
            for c in (prior.get("cases") or [])
            if str(c.get("requirement_id") or "").startswith("REQ-")
        ]
        print(f"Reusing {len(bench_rows)} benchmark rows from {REPORT_JSON}", flush=True)
    else:
        for req_id, text in load_requirements():
            for dtype in DIAGRAM_TYPES:
                case_dir = OUT_DIR / req_id / dtype
                case_dir.mkdir(parents=True, exist_ok=True)
                bench_rows.append(generate_and_accept(req_id, text, dtype, settings, case_dir))
                print(
                    f"  {req_id}/{dtype}: accepted={bench_rows[-1]['accepted']} retries={bench_rows[-1]['retry_count']}",
                    flush=True,
                )

    golden_sum = summarize(golden_rows, "Golden regression")
    bench_sum = summarize(bench_rows, "Benchmark (requirements.txt × 4 types)")
    neg_total = len(negative_rows)
    neg_rejected = sum(1 for r in negative_rows if r.get("correctly_rejected"))
    negative_sum = {
        "label": "Negative controls (must reject)",
        "total": neg_total,
        "correctly_rejected": neg_rejected,
        "false_accepts": neg_total - neg_rejected,
        "true_negative_rate": round(neg_rejected / max(1, neg_total), 4),
    }
    failures = [r for r in bench_rows + golden_rows if not r["accepted"]]
    false_accepts = [r for r in negative_rows if r["accepted"]]
    payload = {
        "method": (
            "Deterministic Stage-1 JSON (heuristic + concept grounding) → "
            "PlantUML builder → PlantUML -checkonly → render → UML structure rules → "
            "requirement↔UML semantic/traceability. Adaptive repair max "
            f"{MAX_REPAIR}. VLM scoring is a separate paper gate and is not included here."
        ),
        "golden": golden_sum,
        "benchmark": bench_sum,
        "negative_controls": negative_sum,
        "failures": [
            {
                "requirement_id": f["requirement_id"],
                "diagram_type": f["diagram_type"],
                "requirement": f["requirement"],
                "failure_category": f["failure_category"],
                "retry_count": f["retry_count"],
                "messages": f["messages"],
                "missing": (f.get("semantic") or {}).get("missing"),
                "extra": (f.get("semantic") or {}).get("extra"),
            }
            for f in failures
        ],
        "false_accepts": false_accepts,
        "cases": [
            {k: v for k, v in r.items() if k != "generated_plantuml"}
            for r in golden_rows + bench_rows
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md = (
        "# UML acceptance evaluation\n\n"
        f"{payload['method']}\n\n"
        "```text\n"
        + fmt_scoreboard(golden_sum)
        + "\n\n"
        + fmt_scoreboard(bench_sum)
        + "\n\n"
        + f"{negative_sum['label']}\n"
        + f"Total negative controls: {neg_total}\n"
        + f"Correctly rejected: {neg_rejected}/{neg_total}\n"
        + f"False accepts: {neg_total - neg_rejected}\n"
        + f"True-negative rate: {negative_sum['true_negative_rate']}\n"
        + "\n```\n"
    )
    if failures:
        md += "\n## Remaining failures\n\n"
        for f in failures:
            md += (
                f"- `{f['requirement_id']}` / `{f['diagram_type']}` "
                f"[{f['failure_category']}] retries={f['retry_count']}: "
                f"{'; '.join((f['messages'] or [])[:3]) or f['requirement'][:80]}\n"
            )
    REPORT_MD.write_text(md, encoding="utf-8")
    print("\n" + fmt_scoreboard(golden_sum))
    print()
    print(fmt_scoreboard(bench_sum))
    print()
    print(negative_sum["label"])
    print(f"Correctly rejected: {neg_rejected}/{neg_total}")
    print(f"False accepts: {neg_total - neg_rejected}")
    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    ok = golden_sum["remaining_failures"] == 0 and (neg_total - neg_rejected) == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
