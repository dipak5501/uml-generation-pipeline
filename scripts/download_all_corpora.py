#!/usr/bin/env python3
"""
Download and persist ALL known open UML/PlantUML Hugging Face corpora under data/raw/hf/.

Also attempts repo-supported gated downloads via download_datasets.py path.
Does not print tokens. Writes data/raw/hf/download_manifest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uml_pipeline.config import ensure_dirs, load_config

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

# Every open corpus we know of for this project (train + eval / web PlantUML).
ALL_OPEN_REPOS: list[dict[str, Any]] = [
    # Paper / training builder sources
    {"repo": "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW"},
    {"repo": "nguyenvanviet/UMLCode_ObjectDiagram_Scored"},
    {"repo": "nguyenvanviet/UMLCode_ComponentDiagram_Scored"},
    {"repo": "nguyenvanviet/UMLCode_PackageDiagram_Scored"},
    {"repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored"},
    {"repo": "nguyenvanviet/UMLCode_Activity_Final"},
    {"repo": "nguyenvanviet/UMLCode_DeploymentDiagram"},
    # Extra UMLCode open sets
    {"repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-RAW"},
    {"repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-Scored"},
    {"repo": "nguyenvanviet/UMLCode_Sequence_Reasoning-RAW"},
    {"repo": "nguyenvanviet/UMLCode_Sequence_scores"},
    {"repo": "nguyenvanviet/UMLCode_StateDiagram"},
    {"repo": "nguyenvanviet/UMLCode_StateDiagram_Scored"},
    {"repo": "nguyenvanviet/UMLCode_Activity"},
    {"repo": "nguyenvanviet/UMLCode_ObjectDiagram"},
    {"repo": "nguyenvanviet/UMLCode_ComponentDiagram"},
    {"repo": "nguyenvanviet/UMLCode_PackageDiagram"},
    {"repo": "nguyenvanviet/UMLCode_Reasoning_Class_UseCase_Scored"},
    {"repo": "nguyenvanviet/UMLCode_UseCaseDiagram_v1"},
    {"repo": "nguyenkhanh87/UMLCode-DeepSeek-32B-Reasoning-RAW"},
    {"repo": "nguyenkhanh87/UMLCode-DeepSeek-32B-Reasoning-Scored"},
    # External PlantUML open corpora
    {"repo": "coai/plantuml_generation"},
    {"repo": "ibivibiv/plantuml-training"},
    {"repo": "prashant182/plantuml-json"},
    {"repo": "ThePeaceLovingGhost/ClassDiagram_PlantUML_Text"},
    {"repo": "vinzur/Prompt-to-PlantUML"},
    {"repo": "vinzur/softw-desc-to-plantuml-usecase-diagram"},
    {"repo": "vinzur/user-stories-to-plantuml-usecase-diagram"},
    {"repo": "Seym0n/cas2uml_hand-drawn_to_plantuml_dataset"},
    {"repo": "josoa-test/plantuml-datasets"},
    {"repo": "devgpt-aimotion/the-stack-v2_PlantUML_filtered"},
    {"repo": "devgpt-aimotion/the-stack-v2_PlantUML_full"},
]

GATED_REPOS = [
    "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Scored",
]

# Known-broken / empty data files — still attempt, record failure
KNOWN_FLAKY = [
    "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Raw",
    "jg512/repo-plantuml-dataset",
]


def _slug(repo: str) -> str:
    return repo.replace("/", "__")


def _token() -> str | None:
    return os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN") or None


def _drop_heavy_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Drop image/binary columns so local parquet stays manageable."""
    drop = [c for c in df.columns if c.lower() in {"image", "images", "audio", "video"}]
    if drop:
        df = df.drop(columns=drop, errors="ignore")
    return df


def download_repo(repo: str, out_dir: Path, split: str = "train") -> dict[str, Any]:
    token = _token()
    kwargs: dict[str, Any] = {"token": token} if token else {}
    print(f"Downloading {repo} ({split}) …")
    try:
        ds = load_dataset(repo, split=split, **kwargs)
    except Exception as exc:
        return {
            "repo": repo,
            "split": split,
            "ok": False,
            "error": f"{type(exc).__name__}: {str(exc).splitlines()[0][:240]}",
            "rows": 0,
        }

    df = ds.to_pandas()
    df = _drop_heavy_cols(df)
    dest = out_dir / _slug(repo)
    dest.mkdir(parents=True, exist_ok=True)
    parquet_path = dest / f"{split}.parquet"
    # Some frames have nested/object cols that parquet hates — fall back to jsonl
    try:
        df.to_parquet(parquet_path, index=False)
        primary = str(parquet_path)
    except Exception:
        jsonl_path = dest / f"{split}.jsonl"
        df.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)
        primary = str(jsonl_path)
        parquet_path = None

    meta = {
        "repo": repo,
        "split": split,
        "ok": True,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "path": primary,
        "bytes": int(Path(primary).stat().st_size) if Path(primary).is_file() else 0,
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  -> {meta['rows']} rows ({meta['bytes']/1e6:.1f} MB) → {primary}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Download all UML/PlantUML HF corpora locally")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "hf",
    )
    parser.add_argument(
        "--skip-full-stack",
        action="store_true",
        help="Skip the-stack-v2_PlantUML_full (~109k) to save disk/time",
    )
    parser.add_argument("--also-gated", action="store_true", default=True)
    parser.add_argument("--no-gated", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    ensure_dirs(cfg)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    repos = list(ALL_OPEN_REPOS)
    for r in KNOWN_FLAKY:
        repos.append({"repo": r})
    if args.also_gated and not args.no_gated:
        for r in GATED_REPOS:
            repos.append({"repo": r, "gated": True})

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for meta in repos:
        repo = meta["repo"]
        if repo in seen:
            continue
        seen.add(repo)
        if args.skip_full_stack and "PlantUML_full" in repo:
            results.append(
                {
                    "repo": repo,
                    "ok": False,
                    "skipped": True,
                    "error": "skipped via --skip-full-stack",
                    "rows": 0,
                }
            )
            continue
        results.append(download_repo(repo, args.out_dir))
        # Also persist test split when present (e.g. Seym0n)
        if results[-1].get("ok") and repo.startswith("Seym0n/"):
            results.append(download_repo(repo, args.out_dir, split="test"))

    # Repo-supported merge path (config.yaml datasets)
    print("\n=== download_datasets.py path (config.yaml) ===")
    try:
        from uml_pipeline.datasets import download_all

        download_all(
            cfg,
            skip_errors=True,
            include_gated=not args.no_gated,
        )
        results.append(
            {
                "repo": "__config_download_all__",
                "ok": True,
                "note": "Wrote data/raw/*.parquet + data/uml_design_dataset.parquet",
            }
        )
    except Exception as exc:
        results.append(
            {
                "repo": "__config_download_all__",
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )

    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok") and not r.get("skipped")]
    manifest = {
        "out_dir": str(args.out_dir),
        "ok_count": len(ok),
        "fail_count": len(fail),
        "total_rows_ok": sum(int(r.get("rows") or 0) for r in ok),
        "results": results,
    }
    man_path = args.out_dir / "download_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest → {man_path}")
    print(f"OK={len(ok)} FAIL={len(fail)} rows_sum≈{manifest['total_rows_ok']}")
    if fail:
        print("Failures:")
        for r in fail:
            print(f"  - {r.get('repo')}: {r.get('error')}")


if __name__ == "__main__":
    main()
