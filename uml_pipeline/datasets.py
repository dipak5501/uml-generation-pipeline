from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset

from uml_pipeline.scoring import recompute_composite


def _hf_token() -> str | None:
    return os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN") or None


def load_hf_dataset(repo: str):
    token = _hf_token()
    kwargs = {"token": token} if token else {}
    try:
        return load_dataset(repo, split="train", **kwargs)
    except Exception as exc:
        msg = str(exc).lower()
        if "gated" in msg or "authenticated" in msg:
            raise RuntimeError(
                f"Dataset '{repo}' requires Hugging Face access.\n"
                f"  1. Accept the license: https://huggingface.co/datasets/{repo}\n"
                "  2. Create a token: https://huggingface.co/settings/tokens\n"
                "  3. Set HF_TOKEN in your .env file"
            ) from exc
        raise


def download_all(
    cfg: dict[str, Any],
    limit_per_type: int | None = None,
    only_types: list[str] | None = None,
    skip_errors: bool = False,
    include_gated: bool = False,
) -> Path:
    """Download optional Hugging Face benchmark datasets and merge to unified parquet."""
    data_dir = Path(cfg["data_dir"])
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    weights = cfg["vlm_weights"]
    errors: list[str] = []

    for key, meta in cfg["datasets"].items():
        diagram_type = meta["diagram_type"]
        # Skip gated optional entries unless --include-gated or --only class
        if key.endswith("_gated") and not include_gated and not only_types:
            print(
                f"Skipping gated dataset key '{key}' "
                f"(pass --include-gated or --only {diagram_type} after accepting license + HF_TOKEN)"
            )
            continue
        if only_types and diagram_type not in only_types:
            continue

        repo = meta["repo"]
        print(f"Loading {repo} ...")
        try:
            ds = load_hf_dataset(repo)
        except Exception as exc:
            errors.append(f"{diagram_type}: {exc}")
            if skip_errors:
                print(f"  SKIP ({exc})")
                continue
            raise

        df = ds.to_pandas()
        df["diagram_type"] = diagram_type
        df["source_dataset"] = repo

        if limit_per_type:
            df = df.head(limit_per_type)

        if "scores" not in df.columns or df["scores"].isna().any():
            df["scores_recomputed"] = df.apply(
                lambda r: recompute_composite(r.to_dict(), weights), axis=1
            )
        frames.append(df)

        out_single = raw_dir / f"{diagram_type}.parquet"
        df.to_parquet(out_single, index=False)
        print(f"  -> {len(df)} rows saved to {out_single}")

    if not frames:
        raise RuntimeError(
            "No datasets downloaded.\n" + "\n".join(errors) if errors else "No datasets matched."
        )

    merged = pd.concat(frames, ignore_index=True)
    merged_path = data_dir / "uml_design_dataset.parquet"
    merged.to_parquet(merged_path, index=False)

    manifest = {
        "total_rows": len(merged),
        "by_type": merged["diagram_type"].value_counts().to_dict(),
        "columns": list(merged.columns),
        "datasets": {k: v["repo"] for k, v in cfg["datasets"].items()},
    }
    (data_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Merged dataset: {merged_path} ({len(merged)} rows)")
    if errors:
        print("Warnings:")
        for e in errors:
            print(f"  - {e}")
    return merged_path


def load_merged(cfg: dict[str, Any]) -> pd.DataFrame:
    path = Path(cfg["data_dir"]) / "uml_design_dataset.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Run: python scripts/download_datasets.py"
        )
    return pd.read_parquet(path)


def export_jsonl(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", lines=True, force_ascii=False)
