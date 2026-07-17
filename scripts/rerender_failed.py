#!/usr/bin/env python3
"""Re-render failed artifacts (uses remote PlantUML if Java is missing) and rescore."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import RenderAttempt, UMLArtifact
from app.services.orchestration import apply_verification, score_image
from app.services.scoring import verify_scores
from app.settings import get_settings
from uml_pipeline.render import render_plantuml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 = all failed")
    parser.add_argument("--all", action="store_true", help="Re-render all artifacts")
    args = parser.parse_args()

    settings = get_settings()
    init_db()
    ok = fail = 0
    with Session(get_engine()) as session:
        q = select(UMLArtifact)
        arts = session.exec(q).all()
        if not args.all:
            arts = [a for a in arts if a.render_status != "success"]
        if args.limit:
            arts = arts[: args.limit]

        for a in arts:
            out_dir = settings.artifact_dir / str(a.id)
            out_dir.mkdir(parents=True, exist_ok=True)
            img, err = render_plantuml(
                a.plantuml_code, out_dir, settings.plantuml_jar, fmt=settings.image_format
            )
            session.add(
                RenderAttempt(
                    artifact_id=a.id,
                    attempt_number=1,
                    success=img is not None,
                    error_output=err,
                    image_path=str(img) if img else None,
                    fmt=settings.image_format,
                )
            )
            if img is None:
                a.render_status = "failed"
                a.image_path = None
                zero = {k: 0 for k in settings.vlm_weight_map}
                meta = {
                    k: {
                        "model_name": k,
                        "available": True,
                        "explanation": err or "render failed",
                        "raw_output": None,
                    }
                    for k in zero
                }
                verification = verify_scores(
                    zero,
                    settings.vlm_weight_map,
                    render_ok=False,
                    tau=settings.acceptance_tau,
                    min_composite=settings.min_composite_for_dataset,
                )
                apply_verification(a, zero, meta, verification, session, clear_existing=True)
                fail += 1
                print(f"FAIL id={a.id}: {err}")
            else:
                import shutil

                stable = out_dir / f"diagram.{settings.image_format}"
                if Path(img) != stable:
                    shutil.copy2(img, stable)
                a.image_path = str(stable)
                a.render_status = "success"
                scores, meta, _ = score_image(stable, a.technical_spec, settings)
                verification = verify_scores(
                    scores,
                    settings.vlm_weight_map,
                    render_ok=True,
                    tau=settings.acceptance_tau,
                    min_composite=settings.min_composite_for_dataset,
                )
                apply_verification(a, scores, meta, verification, session, clear_existing=True)
                ok += 1
                print(
                    f"OK   id={a.id} score={verification.composite:.2f} "
                    f"majority={verification.majority_accepted} dataset={verification.dataset_accepted}"
                )
            session.add(a)
            session.commit()
    print(f"Done. success={ok} failed={fail}")


if __name__ == "__main__":
    main()
