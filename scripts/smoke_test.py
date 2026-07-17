#!/usr/bin/env python3
"""End-to-end smoke test: all diagram types + source code mode."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

import requests

API = "http://127.0.0.1:8000"
SAMPLE_CODE = '''class User:
    def authenticate(self, password: str) -> bool:
        return True

class Order:
    def total(self) -> float:
        return 0.0
'''


def main() -> int:
    health = requests.get(f"{API}/api/settings/health", timeout=10)
    health.raise_for_status()
    print("Health:", health.json().get("provider_summary") or health.json().get("provider"))

    failures = 0
    for dtype in ["class", "object", "component", "package", "flowchart"]:
        r = requests.post(
            f"{API}/api/generate",
            json={
                "requirement": "Hospital appointments with patients, doctors, and clinics.",
                "diagram_type": dtype,
                "input_mode": "requirement",
            },
            timeout=180,
        )
        if r.status_code != 200:
            print(f"FAIL {dtype}: HTTP {r.status_code} {r.text[:200]}")
            failures += 1
            continue
        art = r.json()["artifact"]
        ok = art["render_status"] == "success" and "@startuml" in art["plantuml_code"].lower()
        print(
            f"{'OK' if ok else 'FAIL'} {dtype}: render={art['render_status']} "
            f"score={art['composite_score']:.2f} lang={art.get('source_language')}"
        )
        if not ok:
            failures += 1
            print("  validation:", art.get("validation_messages"))

    r = requests.post(
        f"{API}/api/generate",
        json={"requirement": SAMPLE_CODE, "diagram_type": "class", "input_mode": "source_code"},
        timeout=180,
    )
    if r.status_code != 200:
        print(f"FAIL source_code: HTTP {r.status_code}")
        failures += 1
    else:
        art = r.json()["artifact"]
        ok = (
            art["render_status"] == "success"
            and art.get("input_mode") == "source_code"
            and art.get("source_language") == "python"
        )
        print(f"{'OK' if ok else 'FAIL'} source_code: render={art['render_status']} lang={art.get('source_language')}")
        if not ok:
            failures += 1

    if failures:
        print(f"\nSmoke test FAILED ({failures} cases)")
        return 1
    print("\nSmoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
