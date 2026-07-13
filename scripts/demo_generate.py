#!/usr/bin/env python3
"""Generate a small demo dataset via the in-process orchestration (mock-friendly)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session

from app.db import get_engine, init_db
from app.services.orchestration import get_or_create_default_project, run_single_generation
from app.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=1, help="Requirements per diagram type")
    args = parser.parse_args()

    settings = get_settings()
    init_db()
    req_path = Path(__file__).resolve().parent.parent / "sample_data" / "requirements.txt"
    requirements = [ln.strip() for ln in req_path.read_text().splitlines() if ln.strip()][: args.n]

    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)
        for req in requirements:
            for dtype in ("class", "object", "component", "package"):
                art = run_single_generation(
                    session,
                    requirement=req,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                )
                print(
                    f"artifact={art.id} type={dtype} render={art.render_status} "
                    f"score={art.composite_score:.3f}"
                )


if __name__ == "__main__":
    main()
