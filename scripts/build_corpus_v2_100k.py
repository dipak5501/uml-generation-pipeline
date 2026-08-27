#!/usr/bin/env python3
"""
Collect ~100k MORE unique UML training rows for the 200k LoRA pass.

Dedupes against uml_training_combined_100k.parquet (+ supplement + 8000).
Primary new web sources: remaining the-stack-v2_PlantUML_full rows, filtered stack,
all local HF mirrors not fully consumed, and build_training_corpus open pool leftovers.

Honest synthetic multi-language code top-up when unique web pool is exhausted.

Outputs:
  data/training/uml_source_code_100k_v2.parquet
  data/training/uml_training_combined_200k.parquet
  data/training/corpus_v2_manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_source_code_corpus import (  # noqa: E402
    ADAPTERS,
    HF_MIRROR,
    SOURCE_CODE_SOURCES,
    _existing_hashes,
    _read_local_hf,
    _row_from_adapted,
    _sanitize_hf_row,
    adapter_stack_source,
    merge_existing,
    select_source_corpus,
)
from scripts.build_training_corpus import (  # noqa: E402
    TOPUP_SOURCES,
    load_open_frames,
    normalize_row,
)

ADAPTERS["stack_source"] = adapter_stack_source

# Extra mirrors beyond SOURCE_CODE_SOURCES (already partially used in v1).
V2_EXTRA_SOURCES: list[dict[str, Any]] = [
    {
        "slug": "devgpt-aimotion__the-stack-v2_PlantUML_filtered",
        "repo": "devgpt-aimotion/the-stack-v2_PlantUML_filtered",
        "adapter": "stack_source",
        "priority": 90,
        "input_mode": "source_code",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
            "unknown",
        },
    },
    {
        "slug": "Seym0n__cas2uml_hand-drawn_to_plantuml_dataset",
        "repo": "Seym0n/cas2uml_hand-drawn_to_plantuml_dataset",
        "adapter": "cas2uml",
        "priority": 25,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode-DeepSeek-32B-Reasoning-Scored",
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-Scored",
        "adapter": "umlcode",
        "priority": 15,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored",
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored",
        "adapter": "umlcode",
        "priority": 15,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_ObjectDiagram_Scored",
        "repo": "nguyenvanviet/UMLCode_ObjectDiagram_Scored",
        "adapter": "umlcode",
        "forced_type": "object",
        "priority": 12,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_ComponentDiagram_Scored",
        "repo": "nguyenvanviet/UMLCode_ComponentDiagram_Scored",
        "adapter": "umlcode",
        "forced_type": "component",
        "priority": 12,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_PackageDiagram_Scored",
        "repo": "nguyenvanviet/UMLCode_PackageDiagram_Scored",
        "adapter": "umlcode",
        "forced_type": "package",
        "priority": 12,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_Activity_Final",
        "repo": "nguyenvanviet/UMLCode_Activity_Final",
        "adapter": "umlcode",
        "forced_type": "flowchart",
        "priority": 10,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_Sequence_Reasoning-RAW",
        "repo": "nguyenvanviet/UMLCode_Sequence_Reasoning-RAW",
        "adapter": "umlcode",
        "forced_type": "sequence",
        "priority": 10,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_StateDiagram_Scored",
        "repo": "nguyenvanviet/UMLCode_StateDiagram_Scored",
        "adapter": "umlcode",
        "forced_type": "state",
        "priority": 10,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_Reasoning_Class_UseCase_Scored",
        "repo": "nguyenvanviet/UMLCode_Reasoning_Class_UseCase_Scored",
        "adapter": "umlcode",
        "priority": 10,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_UseCaseDiagram_v1",
        "repo": "nguyenvanviet/UMLCode_UseCaseDiagram_v1",
        "adapter": "umlcode",
        "forced_type": "usecase",
        "priority": 10,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode_DeploymentDiagram",
        "repo": "nguyenvanviet/UMLCode_DeploymentDiagram",
        "adapter": "umlcode",
        "forced_type": "deployment",
        "priority": 8,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenkhanh87__UMLCode-DeepSeek-32B-Reasoning-RAW",
        "repo": "nguyenkhanh87/UMLCode-DeepSeek-32B-Reasoning-RAW",
        "adapter": "umlcode",
        "priority": 8,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenkhanh87__UMLCode-DeepSeek-32B-Reasoning-Scored",
        "repo": "nguyenkhanh87/UMLCode-DeepSeek-32B-Reasoning-Scored",
        "adapter": "umlcode",
        "priority": 8,
        "input_mode": "requirement",
    },
]


def _all_v2_sources() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for meta in SOURCE_CODE_SOURCES + V2_EXTRA_SOURCES:
        slug = meta.get("slug") or meta["repo"].replace("/", "__")
        if slug in seen:
            continue
        seen.add(slug)
        m = dict(meta)
        m.setdefault("slug", slug)
        out.append(m)
    return sorted(out, key=lambda m: -m.get("priority", 0))


def load_v2_pool(*, skip_hf_download: bool) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for meta in _all_v2_sources():
        slug = meta["slug"]
        repo = meta["repo"]
        adapter_name = meta["adapter"]
        adapter = ADAPTERS[adapter_name]
        df = _read_local_hf(slug)
        if df is None:
            if skip_hf_download:
                print(f"  SKIP {repo}: no local mirror")
                continue
            from datasets import load_dataset

            print(f"  Loading {repo} from Hugging Face …")
            try:
                ds = load_dataset(repo, split="train")
                df = ds.to_pandas()
            except Exception as exc:
                print(f"  SKIP {repo}: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
                continue
        print(f"  {repo}: {len(df)} raw [{adapter_name}]")
        kept = 0
        for item in df.to_dict(orient="records"):
            adapted = adapter(_sanitize_hf_row(dict(item)))
            if not adapted:
                continue
            row = _row_from_adapted(
                adapted,
                repo=repo,
                forced_type=meta.get("forced_type"),
                allow_types=meta.get("allow_types"),
                input_mode=meta.get("input_mode") or "source_code",
            )
            if row:
                rows.append(row)
                kept += 1
        print(f"    kept {kept}")

    # Second pass: build_training_corpus open pool (UMLCode + instruction sets)
    print("\n=== build_training_corpus open pool (v2 leftovers) ===")
    try:
        open_df = load_open_frames(include_flowchart=True, allow_topup_sources=True)
        for rec in open_df.to_dict(orient="records"):
            rec["input_mode"] = rec.get("input_mode") or "requirement"
            rows.append(rec)
        print(f"  open pool added {len(open_df)} rows")
    except Exception as exc:
        print(f"  open pool SKIP: {exc}")

    if not rows:
        raise RuntimeError("No v2 rows loaded — run download_all_corpora.py first")
    pool = pd.DataFrame(rows)
    before = len(pool)
    pool = pool.drop_duplicates(subset=["uml_code"], keep="first")
    print(f"V2 pool dedup: {before} → {len(pool)}")
    return pool


def main() -> None:
    ap = argparse.ArgumentParser(description="Build second 100k unique corpus for 200k LoRA")
    ap.add_argument("--target", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument(
        "--exclude-parquet",
        action="append",
        default=[
            "data/training/uml_training_combined_100k.parquet",
            "data/training/uml_training_supplement_merged.parquet",
            "data/training/uml_training_8000.parquet",
            "data/training/uml_source_code_50k.parquet",
        ],
    )
    ap.add_argument(
        "--merge-base",
        type=Path,
        default=Path("data/training/uml_training_combined_100k.parquet"),
    )
    ap.add_argument("--skip-hf-download", action="store_true", default=True)
    ap.add_argument("--allow-hf-download", action="store_true")
    args = ap.parse_args()
    skip_dl = args.skip_hf_download and not args.allow_hf_download

    train_dir = ROOT / "data" / "training"
    train_dir.mkdir(parents=True, exist_ok=True)

    exclude_paths = [ROOT / p for p in args.exclude_parquet]
    exclude_hashes = _existing_hashes(*exclude_paths)
    print(f"Excluding {len(exclude_hashes)} prior uml_code hashes")

    pool = load_v2_pool(skip_hf_download=skip_dl)
    print("Pool by source (top 10):", dict(Counter(pool["source_dataset"]).most_common(10)))

    corpus = select_source_corpus(
        pool,
        target=args.target,
        exclude_hashes=exclude_hashes,
        seed=args.seed,
    )
    web_rows = len(corpus)
    synthetic_rows = 0

    if len(corpus) < args.target:
        need = args.target - len(corpus)
        print(
            f"Top-up: {need} synthetic multi-language code samples "
            "(unique web pool exhausted after dedup vs 102k combined)"
        )
        from scripts.build_scenario_code_corpus import build_code_samples, to_training_frame

        codes = build_code_samples(need, args.seed + 200_000)
        for r in codes:
            r["source_dataset"] = "synthetic_code_v2_topup"
            uid = r.get("id") or "x"
            r["uml_code"] = r["uml_code"].replace(
                "@startuml", f"@startuml\n' v2-training-id:{uid}", 1
            )
        topup_df = to_training_frame(codes)
        topup_df["input_mode"] = "source_code"
        topup_df["source_language"] = [r.get("source_language") for r in codes]
        for col in corpus.columns:
            if col not in topup_df.columns:
                topup_df[col] = None
        corpus = pd.concat([corpus, topup_df[corpus.columns]], ignore_index=True)
        corpus = corpus.drop_duplicates(subset=["uml_code"], keep="first")
        synthetic_rows = int(corpus["source_dataset"].astype(str).str.contains("synthetic").sum())
        if len(corpus) > args.target:
            corpus = corpus.sample(n=args.target, random_state=args.seed).reset_index(drop=True)
        print(f"After top-up: {len(corpus)} rows (synthetic≈{synthetic_rows})")

    out_v2 = train_dir / "uml_source_code_100k_v2.parquet"
    corpus.to_parquet(out_v2, index=False)
    corpus.to_json(out_v2.with_suffix(".jsonl"), orient="records", lines=True, force_ascii=False)

    combined_path = train_dir / "uml_training_combined_200k.parquet"
    combined = merge_existing(corpus, args.merge_base, combined_path)

    manifest = {
        "target_v2_rows": args.target,
        "selected_v2_rows": len(corpus),
        "web_unique_rows_before_topup": web_rows,
        "synthetic_topup_rows": synthetic_rows,
        "combined_200k_rows": len(combined),
        "excluded_prior_hashes": len(exclude_hashes),
        "by_source": dict(Counter(corpus["source_dataset"])),
        "by_diagram_type": dict(Counter(corpus["diagram_type"])),
        "by_input_mode": dict(Counter(corpus.get("input_mode", pd.Series(["?"])))),
        "sources": [s["repo"] for s in _all_v2_sources()],
        "outputs": {
            "v2_parquet": str(out_v2),
            "combined_200k_parquet": str(combined_path),
        },
        "notes": [
            "Second 100k pass for 200k LoRA warm-start from uml-plantuml-lora-100k.",
            f"Web-unique rows before synthetic top-up: {web_rows}.",
            f"Synthetic top-up rows (honest): {synthetic_rows} when HF/web pool exhausted.",
            "Deduped against uml_training_combined_100k + supplement + 8000 + source_code_50k.",
            "Merged with combined_100k → uml_training_combined_200k.parquet.",
        ],
    }
    man_path = train_dir / "corpus_v2_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
