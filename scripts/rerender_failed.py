#!/usr/bin/env python3
"""Re-render failed artifacts (uses remote PlantUML if Java is missing) and rescore."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import CompositeScore, ModelScore, RenderAttempt, UMLArtifact
from app.services.orchestration import score_image
from app.services.scoring import formula_snapshot
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
                a.composite_score = 0.0
                a.image_path = None
                fail += 1
                print(f"FAIL id={a.id}: {err}")
            else:
                stable = out_dir / f"diagram.{settings.image_format}"
                if Path(img) != stable:
                    shutil.copy2(img, stable)
                a.image_path = str(stable)
                a.render_status = "success"
                scores, meta, composite = score_image(stable, a.technical_spec, settings)
                a.composite_score = composite
                # replace scores
                for old in session.exec(select(ModelScore).where(ModelScore.artifact_id == a.id)).all():
                    session.delete(old)
                for old in session.exec(select(CompositeScore).where(CompositeScore.artifact_id == a.id)).all():
                    session.delete(old)
                for key, weight in settings.vlm_weight_map.items():
                    m = meta.get(key, {})
                    session.add(
                        ModelScore(
                            artifact_id=a.id,
                            model_key=key,
                            model_name=str(m.get("model_name", key)),
                            score=int(scores.get(key, 0)),
                            weight=weight,
                            available=bool(m.get("available", True)),
                            explanation=m.get("explanation"),
                            raw_output=m.get("raw_output"),
                        )
                    )
                session.add(
                    CompositeScore(
                        artifact_id=a.id,
                        final_score=composite,
                        formula_snapshot=formula_snapshot(scores, settings.vlm_weight_map, composite),
                    )
                )
                ok += 1
                print(f"OK   id={a.id} score={composite:.2f}")
            session.add(a)
            session.commit()
    print(f"Done. success={ok} failed={fail}")


if __name__ == "__main__":
    main()
