#!/usr/bin/env python3
"""Rescore all successful renders in-process with live VLMs (no API auth)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

# Force live providers before Settings is cached (matches running API server).
for _k, _v in {
    "MOCK_PROVIDERS": "false",
    "USE_OLLAMA": "true",
    "USE_HF_INFERENCE": "false",
    "VLM_FAST_MODE": "false",
    "USE_AYA": "true",
    "VLM_AYA_BACKEND": "local",
}.items():
    os.environ.setdefault(_k, _v)

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import ModelScore, UMLArtifact
from app.services.orchestration import apply_verification, score_image
from app.services.scoring import verify_scores
from app.settings import get_settings
from app.security import resolve_artifact_image


def _has_mock_scores(session: Session, artifact_id: int) -> bool:
    rows = session.exec(
        select(ModelScore).where(ModelScore.artifact_id == artifact_id)
    ).all()
    for row in rows:
        text = (row.raw_output or row.explanation or "").lower()
        if "mock vlm" in text:
            return True
    return False


def main() -> None:
    get_settings.cache_clear()
    init_db()
    settings = get_settings()
    if settings.mock_providers:
        raise SystemExit("Refusing to score: MOCK_PROVIDERS is still true")
    if settings.vlm_aya_backend == "local" and not (settings.hf_token or "").strip():
        print("WARNING: HF_TOKEN missing — Aya may be unavailable", flush=True)
    print(
        f"providers mock={settings.mock_providers} ollama={settings.use_ollama} "
        f"summary={settings.provider_summary}",
        flush=True,
    )

    with Session(get_engine()) as session:
        arts = session.exec(
            select(UMLArtifact)
            .where(UMLArtifact.render_status == "success")
            .order_by(UMLArtifact.id)
        ).all()
    print(f"candidates={len(arts)}", flush=True)

    ok = skip = fail = 0
    for i, art in enumerate(arts, 1):
        with Session(get_engine()) as session:
            a = session.get(UMLArtifact, art.id)
            if not a or a.render_status != "success" or not a.image_path:
                continue
            img = resolve_artifact_image(a.image_path, settings.artifact_dir)
            if img is None:
                print(f"[{i}/{len(arts)}] id={a.id} missing image", flush=True)
                fail += 1
                continue

            # Skip only if already has real (non-mock) 3-model scores
            if (
                a.composite_score
                and a.composite_score > 0
                and a.affirmative_votes
                and not _has_mock_scores(session, a.id)
            ):
                print(
                    f"[{i}/{len(arts)}] id={a.id} skip real S={a.composite_score:.2f}",
                    flush=True,
                )
                skip += 1
                continue

            t0 = time.time()
            try:
                scores, meta, _ = score_image(img, a.technical_spec, settings)
                verification = verify_scores(
                    scores,
                    settings.vlm_weight_map,
                    render_ok=True,
                    tau=settings.acceptance_tau,
                    min_composite=settings.min_composite_for_dataset,
                )
                apply_verification(
                    a, scores, meta, verification, session, clear_existing=True
                )
                session.add(a)
                session.commit()
                keys = ",".join(f"{k}={v}" for k, v in scores.items() if v is not None)
                mock = any(
                    "mock vlm" in (m.get("explanation") or "").lower()
                    for m in meta.values()
                )
                ok += 1
                print(
                    f"[{i}/{len(arts)}] id={a.id} type={a.diagram_type} "
                    f"S={a.composite_score:.2f} A={a.majority_accepted} "
                    f"{keys} mock={mock} {time.time()-t0:.0f}s",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"[{i}/{len(arts)}] id={a.id} ERROR {exc}", flush=True)

    print(f"DONE ok={ok} skip={skip} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
