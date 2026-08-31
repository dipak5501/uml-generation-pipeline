#!/usr/bin/env python3
"""Generate a large demo dataset (default 200 artifacts = 50 requirements × 4 types).

Writes into data/uml_app.db so Streamlit → Generated Diagrams can list them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import UMLArtifact
from app.routers.generate import _load_sample_requirements
from app.services.orchestration import get_or_create_default_project, run_single_generation
from app.settings import get_settings

ROOT = Path(__file__).resolve().parent.parent
CODE_CORPUS = ROOT / "data" / "eval" / "code_langs_1000.jsonl"
SAMPLE_CODE = ROOT / "sample_data" / "sample_code.py"


def _load_source_code_cases(limit: int) -> list[tuple[str, str]]:
    """Return (source_text, diagram_type) pairs for source_code mode."""
    allowed = {"class", "object", "component", "package"}
    cases: list[tuple[str, str]] = []
    if CODE_CORPUS.is_file():
        with CODE_CORPUS.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                dtype = (row.get("diagram_type") or "class").strip()
                if dtype not in allowed:
                    continue
                text = (row.get("source_requirement") or "").strip()
                if len(text) < 3:
                    continue
                cases.append((text, dtype))
                if len(cases) >= limit:
                    return cases
    # Fallback: reuse sample_code.py across types
    fallback = SAMPLE_CODE.read_text(encoding="utf-8") if SAMPLE_CODE.is_file() else (
        "class User:\n    def login(self): pass\nclass Order:\n    def total(self): return 0\n"
    )
    types = ["class", "object", "component", "package"]
    while len(cases) < limit:
        cases.append((fallback, types[len(cases) % 4]))
    return cases[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        type=int,
        default=50,
        help="Number of requirements (× diagram types). Default 50 → 200 artifacts. Use 0 for source_code-only.",
    )
    parser.add_argument(
        "--types",
        default="class,object,component,package",
        help="Comma-separated diagram types",
    )
    parser.add_argument(
        "--skip-vlm",
        action="store_true",
        help="Skip 3-VLM scoring for speed (diagrams still render into DB/UI).",
    )
    parser.add_argument(
        "--source-code",
        type=int,
        default=0,
        metavar="N",
        help="Also generate N artifacts with input_mode=source_code",
    )
    parser.add_argument(
        "--max-repair",
        type=int,
        default=1,
        help="Repair attempts per artifact (default 1).",
    )
    args = parser.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    requirements = _load_sample_requirements(args.n)
    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"max_repair_attempts": args.max_repair})
    init_db()
    total = 0
    ok = 0
    t0 = time.time()
    by_type: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)

        def _one(text: str, dtype: str, mode: str) -> None:
            nonlocal total, ok
            try:
                art = run_single_generation(
                    session,
                    requirement=text,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                    input_mode=mode,
                    skip_vlm=args.skip_vlm,
                )
                total += 1
                by_type[dtype] = by_type.get(dtype, 0) + 1
                by_mode[mode] = by_mode.get(mode, 0) + 1
                if art.render_status == "success":
                    ok += 1
                print(
                    f"[{total}] id={art.id} type={dtype} mode={mode} "
                    f"render={art.render_status} score={float(art.composite_score or 0):.2f}",
                    flush=True,
                )
            except Exception as exc:
                total += 1
                by_type[dtype] = by_type.get(dtype, 0) + 1
                by_mode[mode] = by_mode.get(mode, 0) + 1
                print(
                    f"[{total}] FAIL type={dtype} mode={mode} err={type(exc).__name__}:{exc}",
                    flush=True,
                )

        for req in requirements:
            for dtype in types:
                _one(req, dtype, "requirement")

        if args.source_code > 0:
            for text, dtype in _load_source_code_cases(args.source_code):
                _one(text, dtype, "source_code")

        count = len(session.exec(select(UMLArtifact)).all())
    elapsed = time.time() - t0
    print(
        f"Done. Generated this run: {total} (ok_render={ok}). "
        f"Artifacts in DB: {count}. by_type={by_type} by_mode={by_mode} "
        f"elapsed_s={elapsed:.1f} skip_vlm={args.skip_vlm}",
        flush=True,
    )


if __name__ == "__main__":
    main()
