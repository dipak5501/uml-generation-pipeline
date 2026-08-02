#!/usr/bin/env python3
"""
Live reliability eval: generate diagrams with REAL Ollama VLMs and measure
per-provider availability (the intermittent 1-of-3 / 2-of-3 issue).

Usage:
  PYTHONPATH=. MOCK_PROVIDERS=false USE_OLLAMA=true USE_FINETUNED_CODE=true \\
    python scripts/eval_live_vlm_reliability.py --runs 15
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict  # noqa: F401 — defaultdict used for fail_msgs
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

os.environ["MOCK_PROVIDERS"] = "false"
os.environ["USE_OLLAMA"] = "true"
os.environ.setdefault("USE_FINETUNED_CODE", "true")
os.environ.setdefault("USE_HF_INFERENCE", "false")

from sqlmodel import Session

from app.db import get_engine, init_db
from app.services.orchestration import get_or_create_default_project, run_single_generation
from app.settings import get_settings


CASES = [
    {"requirement": "Library system with Book, Patron, LoanRecord, and Fine tracking.", "diagram_type": "class", "input_mode": "requirement"},
    {"requirement": "Hospital appointments linking Patient, Doctor, Clinic, and Prescription.", "diagram_type": "object", "input_mode": "requirement"},
    {"requirement": "E-commerce checkout with CartService, PaymentService, and InventoryService.", "diagram_type": "component", "input_mode": "requirement"},
    {"requirement": "Banking modules: Accounts, Transactions, and Reporting packages with dependencies.", "diagram_type": "package", "input_mode": "requirement"},
    {"requirement": "Order fulfillment: validate stock, charge payment, ship package, notify customer.", "diagram_type": "flowchart", "input_mode": "requirement"},
    {
        "requirement": "class User:\n    def authenticate(self, password: str) -> bool:\n        return True\n\nclass Order:\n    def total(self) -> float:\n        return 0.0\n",
        "diagram_type": "class",
        "input_mode": "source_code",
    },
    {
        "requirement": "public class Patient { public void book() {} }\npublic class Doctor extends Patient { public void treat() {} }\n",
        "diagram_type": "class",
        "input_mode": "source_code",
    },
    {"requirement": "Sistema de inventario con Producto, Almacen y Pedido.", "diagram_type": "class", "input_mode": "requirement"},
    {"requirement": "Le systeme scolaire gere Etudiant, Cours et Inscription.", "diagram_type": "component", "input_mode": "requirement"},
    {"requirement": "IoT platform with Device, Sensor, Gateway, and Alert entities.", "diagram_type": "object", "input_mode": "requirement"},
    {"requirement": "CRM: Lead, Opportunity, Account, and Activity with clear associations.", "diagram_type": "class", "input_mode": "requirement"},
    {"requirement": "Ticket workflow: create ticket, assign agent, resolve, close.", "diagram_type": "flowchart", "input_mode": "requirement"},
    {"requirement": "Fleet management packages: Vehicles, Drivers, Trips, Maintenance.", "diagram_type": "package", "input_mode": "requirement"},
    {
        "requirement": "class {A} { {ma}() { return true; } }\nclass {B} extends {A} { {mb}() {} }\n".replace("{A}", "Account").replace("{B}", "Savings").replace("{ma}", "open").replace("{mb}", "accrue"),
        "diagram_type": "class",
        "input_mode": "source_code",
    },
    {"requirement": "Restaurant: Customer, MenuItem, Order, Table, Bill relationships.", "diagram_type": "object", "input_mode": "requirement"},
]

KEYS = ["qwen25vl3b", "llama32vl11b", "aya_vision_8b"]


def ensure_dual_ollama() -> None:
    script = ROOT / "scripts" / "ensure_ollama_dual.sh"
    if script.is_file():
        subprocess.run(["bash", str(script)], cwd=str(ROOT), check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=15)
    ap.add_argument("--out", type=Path, default=ROOT / "data/eval/live_vlm_reliability.json")
    args = ap.parse_args()

    ensure_dual_ollama()
    get_settings.cache_clear()
    settings = get_settings().model_copy(
        update={
            "mock_providers": False,
            "use_ollama": True,
            "use_finetuned_code": True,
            "use_hf_inference": False,
            "max_repair_attempts": 1,
        }
    )

    cases = CASES[: max(1, min(args.runs, len(CASES)))]
    init_db()
    rows = []
    avail_counts = Counter()
    avail_by_key = Counter()
    fail_by_key = Counter()
    fail_msgs = defaultdict(Counter)

    print(f"Live VLM reliability runs={len(cases)} mock={settings.mock_providers} ollama={settings.use_ollama}")
    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)
        for i, case in enumerate(cases, 1):
            ensure_dual_ollama()  # keep :11435 alive between heavy runs
            t0 = time.time()
            print(f"[{i}/{len(cases)}] {case['diagram_type']} / {case['input_mode']} …", flush=True)
            try:
                art = run_single_generation(
                    session,
                    requirement=case["requirement"],
                    diagram_type=case["diagram_type"],
                    project_id=project.id,
                    settings=settings,
                    input_mode=case["input_mode"],
                )
                # Reload model scores
                from sqlmodel import select
                from app.models import ModelScore

                scores = session.exec(
                    select(ModelScore).where(ModelScore.artifact_id == art.id)
                ).all()
                per = {}
                n_ok = 0
                for s in scores:
                    available = bool(s.available)
                    per[s.model_key] = {
                        "model_name": s.model_name,
                        "score": s.score,
                        "available": available,
                        "explanation": (s.explanation or "")[:240],
                    }
                    if available:
                        n_ok += 1
                        avail_by_key[s.model_key] += 1
                    else:
                        fail_by_key[s.model_key] += 1
                        msg = (s.explanation or "unavailable")[:160]
                        fail_msgs[s.model_key][msg] += 1
                avail_counts[n_ok] += 1
                row = {
                    "artifact_id": art.id,
                    "diagram_type": case["diagram_type"],
                    "input_mode": case["input_mode"],
                    "render_status": art.render_status,
                    "composite_score": float(art.composite_score or 0),
                    "majority_accepted": bool(art.majority_accepted),
                    "dataset_accepted": bool(art.dataset_accepted),
                    "providers_available": n_ok,
                    "elapsed_s": round(time.time() - t0, 1),
                    "scores": per,
                    "ok": art.render_status == "success" and n_ok >= 1,
                }
            except Exception as exc:
                avail_counts[0] += 1
                for k in KEYS:
                    fail_by_key[k] += 1
                    fail_msgs[k][f"exception:{type(exc).__name__}"] += 1
                row = {
                    "artifact_id": None,
                    "diagram_type": case["diagram_type"],
                    "input_mode": case["input_mode"],
                    "render_status": "error",
                    "composite_score": 0.0,
                    "majority_accepted": False,
                    "dataset_accepted": False,
                    "providers_available": 0,
                    "elapsed_s": round(time.time() - t0, 1),
                    "scores": {},
                    "ok": False,
                    "error": str(exc)[:300],
                }
            rows.append(row)
            print(
                f"  -> render={row['render_status']} providers={row['providers_available']}/3 "
                f"S={row['composite_score']:.2f} {row['elapsed_s']}s",
                flush=True,
            )

    n = len(rows)
    summary = {
        "runs": n,
        "render_success": sum(1 for r in rows if r.get("render_status") == "success"),
        "generation_ok": sum(1 for r in rows if r.get("ok")),
        "provider_availability_histogram": {str(k): v for k, v in sorted(avail_counts.items())},
        "pct_runs_with_3_providers": round(100.0 * avail_counts[3] / n, 1) if n else 0,
        "pct_runs_with_at_least_2": round(100.0 * sum(avail_counts[k] for k in (2, 3)) / n, 1) if n else 0,
        "pct_runs_with_at_least_1": round(100.0 * sum(avail_counts[k] for k in (1, 2, 3)) / n, 1) if n else 0,
        "per_provider_available_rate": {
            k: round(avail_by_key[k] / n, 3) if n else 0 for k in KEYS
        },
        "per_provider_failure_rate": {
            k: round(fail_by_key[k] / n, 3) if n else 0 for k in KEYS
        },
        "top_failure_messages": {
            k: fail_msgs[k].most_common(3) for k in KEYS
        },
        "mean_composite_when_render_ok": (
            sum(r["composite_score"] for r in rows if r.get("render_status") == "success")
            / max(1, sum(1 for r in rows if r.get("render_status") == "success"))
        ),
        "config": {
            "mock_providers": False,
            "use_ollama": True,
            "use_finetuned_code": True,
            "vlm_models": settings.vlm_model_list,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_qwen_base_url": settings.ollama_qwen_base_url,
        },
    }
    report = {"summary": summary, "runs": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary_path = args.out.with_name("live_vlm_reliability_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
