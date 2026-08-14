#!/usr/bin/env python3
"""Pack recent rendered UML artifacts for Google Colab VLM scoring.

Usage (from repo root):
  .venv/bin/python scripts/export_colab_pack.py --limit 20
  → writes data/colab_pack.zip  (upload this in Colab)
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import UMLArtifact
from app.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Export UML PNGs + specs for Colab")
    parser.add_argument("--limit", type=int, default=20, help="Newest successful renders")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output zip path (default: data/colab_pack.zip)",
    )
    args = parser.parse_args()
    settings = get_settings()
    from app.settings import ROOT

    out = args.out or (ROOT / "data" / "colab_pack.zip")
    out.parent.mkdir(parents=True, exist_ok=True)

    init_db()
    items: list[dict] = []
    with Session(get_engine()) as session:
        arts = session.exec(
            select(UMLArtifact)
            .where(UMLArtifact.render_status == "success")
            .order_by(UMLArtifact.id.desc())
            .limit(max(1, args.limit))
        ).all()
        for a in arts:
            img = Path(a.image_path) if a.image_path else None
            if img is None or not img.is_file():
                candidate = settings.artifact_dir / str(a.id) / f"diagram.{a.image_format or 'png'}"
                img = candidate if candidate.is_file() else None
            if img is None:
                continue
            rel = f"images/{a.id}.{img.suffix.lstrip('.') or 'png'}"
            items.append(
                {
                    "artifact_id": a.id,
                    "diagram_type": a.diagram_type,
                    "requirement": (a.source_requirement or "")[:4000],
                    "specification": (a.technical_spec or "")[:8000],
                    "image": rel,
                    "render_status": a.render_status,
                    "local_composite": a.composite_score,
                }
            )
            items[-1]["_src"] = str(img)

    if not items:
        print("No rendered artifacts found. Generate a diagram first.")
        return 1

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = [{k: v for k, v in row.items() if k != "_src"} for row in items]
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for row in items:
            zf.write(row["_src"], row["image"])

    print(f"Wrote {out} ({len(items)} diagrams)")
    print("In Colab: Runtime → GPU, then upload this zip in the notebook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
