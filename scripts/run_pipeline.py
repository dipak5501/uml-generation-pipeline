#!/usr/bin/env python3
"""Run the full UML pipeline: download → analyze → render → (optional) generate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_step(name: str, cmd: list[str]) -> dict:
    print(f"\n{'=' * 60}\n>>> {name}\n{'=' * 60}")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return {
        "step": name,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full UML pipeline")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per diagram type")
    parser.add_argument("--render-limit", type=int, default=50, help="Max diagrams to render")
    parser.add_argument("--generate", type=int, default=0, help="New samples per type (0=skip)")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    steps: list[dict] = []
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": steps}

    if not args.skip_download:
        cmd = [py, "scripts/download_datasets.py", "--skip-errors"]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        steps.append(run_step("1. Download datasets", cmd))

    steps.append(run_step("2. Analyze scores", [py, "scripts/analyze_dataset.py"]))

    render_cmd = [py, "scripts/render_diagrams.py", "--limit", str(args.render_limit)]
    steps.append(run_step("3. Render PlantUML", render_cmd))

    if args.generate > 0:
        for dtype in ("class", "object", "component", "package"):
            steps.append(
                run_step(
                    f"4. Generate {dtype}",
                    [
                        py,
                        "scripts/run_generation.py",
                        "--diagram-type",
                        dtype,
                        "-n",
                        str(args.generate),
                    ],
                )
            )

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["all_ok"] = all(s["ok"] for s in steps)

    out = ROOT / "output" / "pipeline_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved: {out}")
    print(f"Overall: {'SUCCESS' if report['all_ok'] else 'PARTIAL (see report)'}")

    sys.exit(0 if report["all_ok"] else 1)


if __name__ == "__main__":
    main()
