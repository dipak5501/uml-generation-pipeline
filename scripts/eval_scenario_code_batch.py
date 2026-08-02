#!/usr/bin/env python3
"""
Batch evaluation over scenario + multi-language code corpora.

Default: LoRA PlantUML + mock VLMs for speed (checks generation/render/validation).
Optional --live-vlm-sample N runs a stratified live VLM subset.

Examples:
  PYTHONPATH=. python scripts/eval_scenario_code_batch.py --limit 100
  PYTHONPATH=. python scripts/eval_scenario_code_batch.py --all --live-vlm-sample 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sqlmodel import Session

from app.db import get_engine, init_db
from app.services.orchestration import get_or_create_default_project, run_single_generation
from app.settings import get_settings


def _load_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _summarize(results: list[dict]) -> dict:
    by_type: dict[str, Counter] = defaultdict(Counter)
    by_lang: dict[str, Counter] = defaultdict(Counter)
    fail_reasons: Counter = Counter()
    ok = 0
    for r in results:
        key = "ok" if r["ok"] else "fail"
        by_type[r["diagram_type"]][key] += 1
        lang = r.get("source_language") or r.get("human_language") or "n/a"
        by_lang[lang][key] += 1
        if r["ok"]:
            ok += 1
        else:
            fail_reasons[r.get("fail_reason") or "unknown"] += 1
    return {
        "total": len(results),
        "ok": ok,
        "fail": len(results) - ok,
        "ok_rate": (ok / len(results)) if results else 0.0,
        "by_diagram_type": {k: dict(v) for k, v in sorted(by_type.items())},
        "by_language": {k: dict(v) for k, v in sorted(by_lang.items())},
        "fail_reasons": dict(fail_reasons.most_common(20)),
        "mean_composite": (
            sum(r.get("composite_score") or 0 for r in results) / len(results) if results else 0
        ),
    }


def run_cases(
    session: Session,
    project_id: int,
    cases: list[dict],
    *,
    settings,
    mode_field: str,
) -> list[dict]:
    out: list[dict] = []
    for i, case in enumerate(cases, 1):
        dtype = case.get("diagram_type") or "class"
        text = case.get("source_requirement") or ""
        input_mode = case.get("input_mode") or mode_field
        t0 = time.time()
        try:
            art = run_single_generation(
                session,
                requirement=text,
                diagram_type=dtype,
                project_id=project_id,
                settings=settings,
                input_mode=input_mode,
            )
            plantuml = (art.plantuml_code or "").lower()
            render_ok = art.render_status == "success"
            has_uml = "@startuml" in plantuml and "@enduml" in plantuml
            ok = render_ok and has_uml
            fail_reason = None
            if not render_ok:
                fail_reason = f"render:{art.render_status}"
            elif not has_uml:
                fail_reason = "missing_plantuml_markers"
            out.append(
                {
                    "id": case.get("id"),
                    "diagram_type": dtype,
                    "input_mode": art.input_mode,
                    "source_language": art.source_language or case.get("source_language"),
                    "human_language": case.get("human_language"),
                    "ok": ok,
                    "render_status": art.render_status,
                    "composite_score": float(art.composite_score or 0),
                    "majority_accepted": bool(art.majority_accepted),
                    "dataset_accepted": bool(art.dataset_accepted),
                    "elapsed_s": round(time.time() - t0, 2),
                    "fail_reason": fail_reason,
                    "artifact_id": art.id,
                }
            )
        except Exception as exc:
            out.append(
                {
                    "id": case.get("id"),
                    "diagram_type": dtype,
                    "input_mode": input_mode,
                    "source_language": case.get("source_language"),
                    "human_language": case.get("human_language"),
                    "ok": False,
                    "render_status": "error",
                    "composite_score": 0.0,
                    "majority_accepted": False,
                    "dataset_accepted": False,
                    "elapsed_s": round(time.time() - t0, 2),
                    "fail_reason": f"exception:{type(exc).__name__}:{exc}",
                    "artifact_id": None,
                }
            )
        if i % 25 == 0 or i == len(cases):
            print(f"  … {i}/{len(cases)} done", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=ROOT / "data/eval/scenarios_1000.jsonl")
    ap.add_argument("--codes", type=Path, default=ROOT / "data/eval/code_langs_1000.jsonl")
    ap.add_argument("--limit", type=int, default=None, help="Limit each corpus (debug)")
    ap.add_argument("--all", action="store_true", help="Run full 1000+1000")
    ap.add_argument(
        "--live-vlm-sample",
        type=int,
        default=0,
        help="After bulk mock-VLM run, score this many cases live",
    )
    ap.add_argument("--out", type=Path, default=ROOT / "data/eval/batch_report.json")
    args = ap.parse_args()

    limit = None if args.all else (args.limit if args.limit is not None else 50)

    # Bulk: real LoRA + mock providers for VLM/spec speed
    os.environ["MOCK_PROVIDERS"] = "true"
    os.environ["USE_FINETUNED_CODE"] = "true"
    get_settings.cache_clear()
    settings = get_settings()
    settings = settings.model_copy(
        update={
            "mock_providers": True,
            "use_finetuned_code": True,
            "max_repair_attempts": 1,
        }
    )

    scenarios = _load_jsonl(args.scenarios, limit)
    codes = _load_jsonl(args.codes, limit)
    print(f"Evaluating scenarios={len(scenarios)} codes={len(codes)} (mock VLM, LoRA code)")

    init_db()
    engine = get_engine()
    with Session(engine) as session:
        project = get_or_create_default_project(session)
        print("Scenario pass…")
        scen_results = run_cases(
            session, project.id, scenarios, settings=settings, mode_field="requirement"
        )
        print("Code-language pass…")
        code_results = run_cases(
            session, project.id, codes, settings=settings, mode_field="source_code"
        )

    report = {
        "config": {
            "mock_providers": True,
            "use_finetuned_code": True,
            "limit": limit,
            "scenarios_n": len(scenarios),
            "codes_n": len(codes),
        },
        "scenarios": _summarize(scen_results),
        "codes": _summarize(code_results),
        "scenario_results": scen_results,
        "code_results": code_results,
    }

    if args.live_vlm_sample > 0:
        os.environ["MOCK_PROVIDERS"] = "false"
        os.environ["USE_OLLAMA"] = "true"
        get_settings.cache_clear()
        live_settings = get_settings().model_copy(
            update={
                "mock_providers": False,
                "use_ollama": True,
                "use_finetuned_code": True,
                "max_repair_attempts": 1,
            }
        )
        sample = scenarios[: args.live_vlm_sample // 2] + codes[: args.live_vlm_sample - args.live_vlm_sample // 2]
        print(f"Live VLM sample n={len(sample)}…")
        with Session(engine) as session:
            project = get_or_create_default_project(session)
            live_results = run_cases(
                session, project.id, sample, settings=live_settings, mode_field="requirement"
            )
        report["live_vlm_sample"] = _summarize(live_results)
        report["live_vlm_results"] = live_results

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Compact file without full per-row dumps if huge? Keep them for analysis.
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary_path = args.out.with_name("batch_report_summary.json")
    summary = {
        "scenarios": report["scenarios"],
        "codes": report["codes"],
        "live_vlm_sample": report.get("live_vlm_sample"),
        "config": report["config"],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")
    print(f"Wrote {summary_path}")
    scen_ok = report["scenarios"]["ok_rate"] >= 0.85
    code_ok = report["codes"]["ok_rate"] >= 0.85
    return 0 if scen_ok and code_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
