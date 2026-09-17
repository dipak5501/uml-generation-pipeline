#!/usr/bin/env python3
"""
Merge usable on-disk training parquets into one deduped corpus for LoRA.

Primary inputs (supersets preferred; nested subsets omitted):
  - uml_training_combined_sourcecode_30k.parquet  (historical combined + source 30k)
  - uml_in_the_wild_app.parquet                   (UML-in-the-Wild, app diagram types)
  - uml_industrial_enriched_mix.parquet          (industrial enriched mix)
  - uml_adaptation_mix.parquet                   (adaptation / self-train mix)
  - uml_accepted_live_topup.parquet              (live accepted harvest)

Dedupes on SHA1 of stripped uml_code. Writes:
  data/training/uml_training_all_merged.parquet
  data/training/uml_training_all_merged_manifest.json

Does not touch FINETUNED_ADAPTER_PATH / live API.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Order = priority when keeping first occurrence after dedupe.
SOURCES: list[tuple[str, str]] = [
    (
        "combined_sourcecode_30k",
        "data/training/uml_training_combined_sourcecode_30k.parquet",
    ),
    ("wild_app", "data/training/uml_in_the_wild_app.parquet"),
    ("industrial_enriched", "data/training/uml_industrial_enriched_mix.parquet"),
    ("adaptation_mix", "data/training/uml_adaptation_mix.parquet"),
    ("accepted_live_topup", "data/training/uml_accepted_live_topup.parquet"),
]

# Nested / redundant corpora intentionally skipped (almost entirely inside a primary):
SKIPPED_NESTED = [
    "uml_training_combined_200k.parquet",
    "uml_training_combined_100k.parquet",
    "uml_training_8000.parquet",
    "uml_training_supplement_merged.parquet",
    "uml_source_code_100k_v2.parquet",
    "uml_source_code_50k.parquet",
    "uml_source_code_30k_jpc.parquet",
    "uml_source_code_10k_jpc.parquet",
    "uml_source_code_{java,python,c}_10000.parquet",
    "uml_industrial_complete.parquet",  # subset of enriched mix lineage
    "uml_in_the_wild.parquet",  # full wild; app slice used instead
    "uml_open_source_uml_topup.parquet",  # empty / already folded into enriched
]

OUT_PARQUET = ROOT / "data" / "training" / "uml_training_all_merged.parquet"
OUT_MANIFEST = ROOT / "data" / "training" / "uml_training_all_merged_manifest.json"

CORE_COLS = [
    "diagram_type",
    "input_mode",
    "source_language",
    "source_requirement",
    "technical_spec",
    "uml_code",
    "dataset_accepted",
    "majority_accepted",
    "source_dataset",
    "merge_source",
]


def _uml_hash(code: object) -> str:
    text = str(code or "").strip()
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_frame(df: pd.DataFrame, merge_source: str) -> pd.DataFrame:
    out = df.copy()
    if "technical_spec" not in out.columns and "source_requirement" in out.columns:
        out["technical_spec"] = out["source_requirement"]
    if "source_requirement" not in out.columns and "technical_spec" in out.columns:
        out["source_requirement"] = out["technical_spec"]
    if "diagram_type" not in out.columns:
        out["diagram_type"] = "class"
    if "input_mode" not in out.columns:
        out["input_mode"] = "requirement"
    if "source_language" not in out.columns:
        out["source_language"] = ""
    if "dataset_accepted" not in out.columns:
        out["dataset_accepted"] = False
    if "majority_accepted" not in out.columns:
        out["majority_accepted"] = False
    if "source_dataset" not in out.columns:
        out["source_dataset"] = merge_source
    out["merge_source"] = merge_source
    # Keep only columns we need (+ extras dropped)
    for col in CORE_COLS:
        if col not in out.columns:
            out[col] = None if col not in ("dataset_accepted", "majority_accepted") else False
    return out[CORE_COLS]


def main() -> None:
    source_stats: list[dict] = []
    frames: list[pd.DataFrame] = []

    for label, rel in SOURCES:
        path = ROOT / rel
        if not path.is_file():
            source_stats.append(
                {"label": label, "path": rel, "rows": 0, "status": "missing"}
            )
            print(f"SKIP missing: {rel}", file=sys.stderr)
            continue
        df = pd.read_parquet(path)
        n = len(df)
        source_stats.append(
            {
                "label": label,
                "path": rel,
                "rows": int(n),
                "status": "loaded",
                "bytes": path.stat().st_size,
            }
        )
        print(f"LOAD {label}: {n} rows from {rel}")
        frames.append(_normalize_frame(df, label))

    if not frames:
        raise SystemExit("No source parquets found")

    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    combined["_uml_hash"] = combined["uml_code"].map(_uml_hash)
    # Drop empty UML
    combined = combined[combined["uml_code"].fillna("").astype(str).str.strip().str.len() >= 20]
    combined = combined.drop_duplicates(subset=["_uml_hash"], keep="first")
    after = len(combined)
    hashes_kept = int(combined["_uml_hash"].nunique())
    by_merge = Counter(combined["merge_source"].tolist())
    by_type = Counter(
        combined["diagram_type"].fillna("unknown").astype(str).str.lower().tolist()
    )
    by_mode = Counter(
        combined["input_mode"].fillna("requirement").astype(str).str.lower().tolist()
    )

    # combined_30k is a mixed historical corpus (synthetic + code + scraped).
    claim_note = (
        "Merged corpus mixes synthetic scenario rows, source-code-derived UML, "
        "HF/web PlantUML corpora, UML-in-the-Wild (Zenodo metadata specs — not human "
        "requirements), industrial enriched mix, adaptation mix, and live accepted "
        "harvest. Do NOT claim synthetic or Wild metadata specs are 'www real' "
        "human requirements."
    )

    combined = combined.drop(columns=["_uml_hash"])
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(OUT_PARQUET, index=False)

    manifest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "output_parquet": str(OUT_PARQUET.relative_to(ROOT)),
        "rows_before_dedupe": before,
        "rows_after_dedupe": after,
        "unique_uml_hashes": hashes_kept,
        "deduped_away": before - after,
        "by_merge_source_kept": dict(by_merge),
        "by_diagram_type": dict(by_type),
        "by_input_mode": dict(by_mode),
        "sources_loaded": source_stats,
        "skipped_nested_or_redundant": SKIPPED_NESTED,
        "dedupe_key": "sha1(strip(uml_code))",
        "claim_hygiene": claim_note,
        "live_adapter_unchanged": True,
        "recommended_finetune_dir": "data/finetune_all",
        "recommended_adapter": "models/uml-plantuml-lora-all",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in (
        "rows_before_dedupe", "rows_after_dedupe", "deduped_away",
        "by_merge_source_kept", "output_parquet",
    )}, indent=2))
    print(f"Wrote {OUT_PARQUET} ({after} rows)")
    print(f"Wrote {OUT_MANIFEST}")


if __name__ == "__main__":
    main()
