#!/usr/bin/env python3
"""Generate a large demo dataset (default 200 artifacts = 50 requirements × 4 types)."""

from __future__ import annotations

import argparse
import sys
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        type=int,
        default=50,
        help="Number of requirements (× diagram types). Default 50 → 200 artifacts.",
    )
    parser.add_argument(
        "--types",
        default="class,object,component,package,flowchart",
        help="Comma-separated diagram types",
    )
    args = parser.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    requirements = _load_sample_requirements(args.n)
    settings = get_settings().model_copy(update={"max_repair_attempts": 0})
    init_db()
    total = 0
    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)
        for req in requirements:
            for dtype in types:
                art = run_single_generation(
                    session,
                    requirement=req,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                )
                total += 1
                print(
                    f"[{total}] id={art.id} type={dtype} render={art.render_status} "
                    f"score={art.composite_score:.2f}"
                )
        count = len(session.exec(select(UMLArtifact)).all())
    print(f"Done. Generated this run: {total}. Artifacts in DB: {count}")


if __name__ == "__main__":
    main()
