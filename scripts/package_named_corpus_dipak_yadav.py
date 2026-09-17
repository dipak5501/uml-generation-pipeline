#!/usr/bin/env python3
"""
Package the merged all-corpora training parquet as a named release for
future researchers: Dipak_Yadav_UML_PlantUML_All_Corpus_v1.

Writes under:
  data/corpora/Dipak_Yadav_UML_PlantUML_All_Corpus_v1/

Does not touch live .env / production adapter.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_PARQUET = ROOT / "data" / "training" / "uml_training_all_merged.parquet"
SRC_MANIFEST = ROOT / "data" / "training" / "uml_training_all_merged_manifest.json"
OUT_DIR = ROOT / "data" / "corpora" / "Dipak_Yadav_UML_PlantUML_All_Corpus_v1"
NAME = "Dipak_Yadav_UML_PlantUML_All_Corpus_v1"
OUT_PARQUET = OUT_DIR / f"{NAME}.parquet"


def _hardlink_or_copy(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def main() -> None:
    if not SRC_PARQUET.is_file():
        raise SystemExit(
            f"Missing {SRC_PARQUET}. Run: python scripts/merge_all_training_corpora.py"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "samples").mkdir(exist_ok=True)

    link_mode = _hardlink_or_copy(SRC_PARQUET, OUT_PARQUET)
    print(f"Parquet → {OUT_PARQUET} ({link_mode})")

    if SRC_MANIFEST.is_file():
        shutil.copy2(SRC_MANIFEST, OUT_DIR / "manifest.json")
    else:
        print("WARN: no merge manifest; skip manifest.json")

    df = pd.read_parquet(SRC_PARQUET)
    schema = {
        "columns": {c: str(df[c].dtype) for c in df.columns},
        "nrows": int(len(df)),
    }
    (OUT_DIR / "schema.json").write_text(json.dumps(schema, indent=2) + "\n")

    by_diagram = df["diagram_type"].value_counts(dropna=False).to_dict()
    by_input = {
        (k if k is not None and str(k) != "nan" else "null"): int(v)
        for k, v in df["input_mode"].value_counts(dropna=False).items()
    }
    by_merge = (
        df["merge_source"].value_counts(dropna=False).to_dict()
        if "merge_source" in df.columns
        else {}
    )

    meta = {
        "name": NAME,
        "title": "Dipak Yadav UML→PlantUML Combined Training Corpus (v1)",
        "version": "1.0.0",
        "creator": {
            "name": "Dipak Yadav",
            "email": "dipak.yadav5501@gmail.com",
            "affiliation": (
                "California State University, Long Beach — "
                "Computer Engineering & Computer Science (CECS)"
            ),
            "thesis_chair": "Yutong Zhao, Ph.D.",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "nrows": int(len(df)),
        "ncolumns": int(len(df.columns)),
        "columns": list(df.columns),
        "by_diagram_type": {str(k): int(v) for k, v in by_diagram.items()},
        "by_input_mode": by_input,
        "by_merge_source": {str(k): int(v) for k, v in by_merge.items()},
        "parquet_file": OUT_PARQUET.name,
        "parquet_link_mode": link_mode,
        "source_parquet": str(SRC_PARQUET.relative_to(ROOT)),
        "repository": "https://github.com/dipak5501/uml-generation-pipeline",
        "related_adapter": "models/uml-plantuml-lora-all",
        "dedupe": "sha1(strip(uml_code))",
        "license_note": (
            "Aggregated corpus. Underlying rows inherit licenses from their sources "
            "(Hugging Face / Stack PlantUML per-file licenses, Zenodo UML-in-the-Wild, "
            "synthetic rows generated for this thesis project). Redistributors must "
            "respect upstream licenses; filter no_license rows before commercial use."
        ),
        "claim_hygiene": (
            "Mixes mined PlantUML, source-code-derived UML, HF/web corpora, "
            "UML-in-the-Wild (Zenodo; metadata-derived specs — not human requirements), "
            "industrial mixes, adaptation data, and synthetic top-ups. Do NOT claim all "
            "rows are human-authored NL→UML instruction pairs."
        ),
    }
    (OUT_DIR / "release_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    sample = df.sample(n=min(20, len(df)), random_state=42)
    sample_path = OUT_DIR / "samples" / "sample_20.jsonl"
    with sample_path.open("w", encoding="utf-8") as f:
        for rec in sample.to_dict(orient="records"):
            clean = {
                k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                for k, v in rec.items()
            }
            f.write(json.dumps(clean, ensure_ascii=False, default=str) + "\n")

    # README + CITATION are maintained as tracked markdown; refresh only if missing.
    readme = OUT_DIR / "README.md"
    citation = OUT_DIR / "CITATION.md"
    if not readme.is_file() or readme.stat().st_size == 0:
        raise SystemExit(
            f"{readme} missing or empty — keep the hand-authored README in git."
        )
    if not citation.is_file() or citation.stat().st_size == 0:
        raise SystemExit(f"{citation} missing or empty — keep CITATION.md in git.")

    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR.relative_to(ROOT)),
                "nrows": meta["nrows"],
                "parquet_link_mode": link_mode,
                "by_input_mode": by_input,
                "by_merge_source": meta["by_merge_source"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
