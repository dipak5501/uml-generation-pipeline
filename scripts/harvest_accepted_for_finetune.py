#!/usr/bin/env python3
"""Harvest high-quality live artifacts into a training top-up parquet (DB untouched).

Selects dataset_accepted / majority_accepted / human-reviewed renders from the live
SQLite DB and writes:
  data/training/uml_accepted_live_topup.parquet
  data/training/uml_accepted_live_topup.jsonl
  data/training/accepted_harvest_manifest.json

Does not delete or modify data/uml_app.db or data/artifacts/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from app.db import get_engine
from app.models import HumanReview, UMLArtifact
from app.settings import ROOT

DEFAULT_OUT = ROOT / "data" / "training" / "uml_accepted_live_topup.parquet"
DEFAULT_JSONL = ROOT / "data" / "training" / "uml_accepted_live_topup.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "training" / "accepted_harvest_manifest.json"


def _uml_fingerprint(code: str) -> str:
    norm = "\n".join(line.strip() for line in (code or "").splitlines() if line.strip())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def _row_from_artifact(a: UMLArtifact, *, human_boost: bool) -> dict[str, Any] | None:
    spec = (a.technical_spec or "").strip()
    uml = (a.plantuml_code or "").strip()
    if len(spec) < 40 or "@startuml" not in uml.lower() or len(uml) < 20:
        return None
    if a.render_status != "success":
        return None
    return {
        "artifact_id": a.id,
        "diagram_type": (a.diagram_type or "class").strip().lower(),
        "input_mode": (a.input_mode or "requirement").strip().lower(),
        "source_language": a.source_language,
        "source_requirement": a.source_requirement or "",
        "technical_spec": spec,
        "uml_code": uml,
        "scores": float(a.composite_score or 0.0),
        "majority_accepted": bool(a.majority_accepted),
        "affirmative_votes": int(a.affirmative_votes or 0),
        "dataset_accepted": bool(a.dataset_accepted),
        "human_reviewed": bool(human_boost),
        "source_dataset": "live_accepted_harvest",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def harvest(
    *,
    min_composite: float = 3.0,
    include_majority_only: bool = True,
    prefer_human: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    engine = get_engine()
    with Session(engine) as session:
        human_ids: set[int] = set()
        if prefer_human:
            for hr in session.exec(select(HumanReview)).all():
                if hr.artifact_id is not None:
                    human_ids.add(int(hr.artifact_id))

        arts = session.exec(
            select(UMLArtifact).where(UMLArtifact.render_status == "success")
        ).all()

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats = {
        "scanned": len(arts),
        "dataset_accepted": 0,
        "majority_only": 0,
        "human_reviewed": 0,
        "skipped_low_score": 0,
        "skipped_invalid": 0,
        "deduped": 0,
    }

    # Prefer dataset_accepted, then majority_accepted, then human-reviewed.
    ordered = sorted(
        arts,
        key=lambda a: (
            0 if a.id in human_ids else 1,
            0 if a.dataset_accepted else 1,
            0 if a.majority_accepted else 1,
            -(a.composite_score or 0.0),
            -(a.id or 0),
        ),
    )

    for a in ordered:
        is_human = a.id in human_ids
        is_ds = bool(a.dataset_accepted)
        is_maj = bool(a.majority_accepted)
        if not (is_ds or (include_majority_only and is_maj) or is_human):
            continue
        if (a.composite_score or 0.0) < min_composite and not is_human:
            stats["skipped_low_score"] += 1
            continue
        row = _row_from_artifact(a, human_boost=is_human)
        if not row:
            stats["skipped_invalid"] += 1
            continue
        fp = _uml_fingerprint(row["uml_code"])
        if fp in seen:
            stats["deduped"] += 1
            continue
        seen.add(fp)
        rows.append(row)
        if is_ds:
            stats["dataset_accepted"] += 1
        elif is_maj:
            stats["majority_only"] += 1
        if is_human:
            stats["human_reviewed"] += 1

    df = pd.DataFrame(rows)
    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(df)),
        "min_composite": min_composite,
        "include_majority_only": include_majority_only,
        "stats": stats,
        "by_diagram_type": (
            df["diagram_type"].value_counts().to_dict() if len(df) else {}
        ),
    }
    return df, meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--min-composite", type=float, default=3.0)
    parser.add_argument(
        "--majority-only",
        action="store_true",
        help="Also include majority_accepted rows that are not yet dataset_accepted.",
    )
    parser.add_argument(
        "--no-majority-only",
        action="store_true",
        help="Restrict to dataset_accepted (+ human-reviewed).",
    )
    args = parser.parse_args()
    include_maj = True
    if args.no_majority_only:
        include_maj = False
    elif args.majority_only:
        include_maj = True

    df, meta = harvest(
        min_composite=args.min_composite,
        include_majority_only=include_maj,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if len(df):
        df.to_parquet(args.out, index=False)
        with args.jsonl.open("w", encoding="utf-8") as f:
            for rec in df.to_dict(orient="records"):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        # Keep empty but valid artifacts for downstream scripts.
        pd.DataFrame(
            columns=[
                "artifact_id",
                "diagram_type",
                "input_mode",
                "source_language",
                "source_requirement",
                "technical_spec",
                "uml_code",
                "scores",
                "majority_accepted",
                "affirmative_votes",
                "dataset_accepted",
                "human_reviewed",
                "source_dataset",
                "created_at",
            ]
        ).to_parquet(args.out, index=False)
        args.jsonl.write_text("", encoding="utf-8")

    meta["parquet"] = str(args.out)
    meta["jsonl"] = str(args.jsonl)
    args.manifest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
