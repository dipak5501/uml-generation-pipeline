#!/usr/bin/env python3
"""Live smoke: POST /api/generate for golden source-code class diagrams."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "source_code_cases.json"
API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_IDS = [
    "SC-JAVA-01",
    "SC-JAVA-02",
    "SC-JAVA-03",
    "SC-PY-01",
    "SC-PY-02",
    "SC-PY-03",
    "SC-C-01",
    "SC-C-02",
    "SC-C-03",
]


def _auth_headers() -> dict[str, str]:
    token = (os.getenv("API_ACCESS_TOKEN") or "").strip()
    if not token:
        print("ERROR: API_ACCESS_TOKEN not set", file=sys.stderr)
        sys.exit(2)
    return {"Authorization": f"Bearer {token}"}


def _load_cases(ids: list[str]) -> list[dict]:
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}
    missing = [i for i in ids if i not in by_id]
    if missing:
        print(f"Unknown case ids: {missing}", file=sys.stderr)
        sys.exit(2)
    return [by_id[i] for i in ids]


def run_case(case: dict, timeout: int) -> dict:
    headers = _auth_headers()
    payload = {
        "requirement": case["source"],
        "diagram_type": case["diagram_type"],
        "input_mode": "source_code",
        "async_mode": False,
    }
    try:
        r = requests.post(f"{API}/api/generate", headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        return {"id": case["id"], "http": None, "error": str(exc)}

    row: dict = {"id": case["id"], "expected_lang": case["language"], "http": r.status_code}
    if r.status_code != 200:
        row["error"] = r.text[:300]
        return row

    art = r.json()["artifact"]
    row.update(
        {
            "render_status": art.get("render_status"),
            "source_language": art.get("source_language"),
            "input_mode": art.get("input_mode"),
            "vlm_score": art.get("composite_score"),
            "majority_accepted": art.get("majority_accepted"),
        }
    )
    return row


def main() -> int:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", default=DEFAULT_IDS, help="Golden case ids")
    ap.add_argument("--timeout", type=int, default=300, help="Per-request timeout (seconds)")
    ap.add_argument("--json", action="store_true", help="Emit JSON lines only")
    args = ap.parse_args()

    health = requests.get(f"{API}/api/settings/health", timeout=15)
    health.raise_for_status()

    cases = _load_cases(args.ids)
    results = [run_case(c, args.timeout) for c in cases]

    if args.json:
        for row in results:
            print(json.dumps(row))
    else:
        print(f"{'ID':<14} {'HTTP':>4} {'render':<10} {'lang':<8} {'VLM':>6}  notes")
        print("-" * 60)
        for row in results:
            if row.get("http") != 200:
                print(f"{row['id']:<14} {str(row.get('http')):>4}  FAIL  {row.get('error', '')[:40]}")
                continue
            lang = row.get("source_language") or "?"
            score = row.get("vlm_score")
            score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
            flag = ""
            if lang != row["expected_lang"]:
                flag += " WRONG_LANG"
            if isinstance(score, (int, float)) and score < 3.0:
                flag += " LOW_SCORE"
            if row.get("render_status") != "success":
                flag += " RENDER_FAIL"
            print(
                f"{row['id']:<14} {row['http']:>4} {row.get('render_status','?'):<10} "
                f"{lang:<8} {score_s:>6}{flag}"
            )

    failures = sum(
        1
        for row in results
        if row.get("http") != 200
        or row.get("render_status") != "success"
        or row.get("source_language") != row.get("expected_lang")
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
