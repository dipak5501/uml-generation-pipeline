#!/usr/bin/env python3
"""Load restored live diagrams into Generated Diagrams (idempotent)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to catalog.json (default: sample_data/gallery_history/catalog.json)",
    )
    args = parser.parse_args()

    from app.db import get_engine, init_db
    from app.services.gallery_history import DEFAULT_CATALOG_DIR, import_gallery_history
    from app.settings import get_settings
    from sqlmodel import Session

    init_db()
    settings = get_settings()
    catalog = args.catalog or (DEFAULT_CATALOG_DIR / "catalog.json")
    with Session(get_engine()) as session:
        result = import_gallery_history(
            session, catalog_path=catalog, artifact_dir=settings.artifact_dir
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
