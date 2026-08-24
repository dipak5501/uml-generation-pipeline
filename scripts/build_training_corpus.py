#!/usr/bin/env python3
"""
Build an ~8000-row training corpus from open Hugging Face UML datasets.

Paper target: 8000 artifacts across class / object / component / package
(prefer up to 2000 per type; top up with extra class rows if other types are short).

Optional: append flowchart/activity rows as an extension.

Examples:
  python scripts/build_training_corpus.py --target 8000
  python scripts/build_training_corpus.py --target 8000 --include-flowchart
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from app.services.scoring import majority_vote_accept, paper_composite, verify_scores
from uml_pipeline.config import ensure_dirs, load_config

load_dotenv()

# Open (non-gated) Hugging Face sources used for the thesis training corpus.
OPEN_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW",
        "forced_type": "class",
        "priority": 10,
    },
    {
        "repo": "nguyenvanviet/UMLCode_ObjectDiagram_Scored",
        "forced_type": "object",
        "priority": 20,
    },
    {
        "repo": "nguyenvanviet/UMLCode_ComponentDiagram_Scored",
        "forced_type": "component",
        "priority": 20,
    },
    {
        "repo": "nguyenvanviet/UMLCode_PackageDiagram_Scored",
        "forced_type": "package",
        "priority": 20,
    },
    {
        # Mixed UC / class / sequence — used to top up class (and rare object/package).
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored",
        "forced_type": None,
        "priority": 5,
        "allow_types": {"class", "object", "component", "package"},
    },
]

FLOWCHART_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode_Activity_Final",
        "forced_type": "flowchart",
        "priority": 15,
    },
]

# Extra open rows used only to top up toward the 8000 target when paper types fall short.
TOPUP_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode_DeploymentDiagram",
        "forced_type": None,
        "priority": 3,
        "allow_types": {"class", "object", "component", "package", "flowchart"},
    },
]

PAPER_TYPES = ("class", "object", "component", "package")
WEIGHTS = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}


def infer_diagram_type(uml_code: str) -> str:
    c = (uml_code or "").lower()
    if "usecase" in c or re.search(r"\bactor\s+", c):
        return "usecase"
    if re.search(r"\bobject\s+\w+", c) or 'object "' in c:
        return "object"
    if "package " in c or 'package "' in c:
        return "package"
    if re.search(r"\bcomponent\s+", c) or re.search(r"\[.+\]\s+as\s+", c):
        return "component"
    if "[*]" in c or re.search(r"\bstate\s+", c):
        return "state"
    if re.search(r"\bnode\s+", c) or "cloud " in c:
        return "deployment"
    if "participant " in c:
        return "sequence"
    # Activity / flowchart heuristics
    if (
        re.search(r"(?m)^\s*start\s*$", c)
        or re.search(r"(?m)^\s*stop\s*$", c)
        or "if (" in c
        or re.search(r"(?m)^\s*:[^;]+;", c)
    ) and "class " not in c:
        return "flowchart"
    if "class " in c or "abstract " in c or "interface " in c or "enum " in c:
        return "class"
    return "unknown"


def _code_hash(uml_code: str) -> str:
    return hashlib.sha1((uml_code or "").strip().encode("utf-8")).hexdigest()


def _to_int_score(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def normalize_row(row: dict[str, Any], *, source: str, diagram_type: str) -> dict[str, Any]:
    scores = {
        "qwen25vl3b": _to_int_score(row.get("qwen25vl3b")),
        "llama32vl11b": _to_int_score(row.get("llama32vl11b")),
        "aya_vision_8b": _to_int_score(row.get("aya_vision_8b")),
    }
    has_any = any(v is not None for v in scores.values())
    render_ok = True  # open scored corpora assume rendered images existed at scoring time
    if has_any:
        verification = verify_scores(scores, WEIGHTS, render_ok=render_ok, tau=4.0, min_composite=3.0)
        composite = verification.composite
        majority = verification.majority_accepted
        votes = verification.affirmative_votes
        dataset_ok = verification.dataset_accepted
    else:
        existing = row.get("scores")
        composite = float(existing) if existing not in (None, "") else paper_composite(
            {k: 0 for k in WEIGHTS}, WEIGHTS, render_ok=False
        )
        majority, votes, _ = majority_vote_accept({k: 0 for k in WEIGHTS}, tau=4.0)
        dataset_ok = False

    return {
        "id": _code_hash(str(row.get("uml_code", "")))[:12],
        "diagram_type": diagram_type,
        "source_requirement": str(row.get("input") or ""),
        "technical_spec": str(row.get("input") or ""),
        "uml_code": str(row.get("uml_code") or ""),
        "reasoning_private": str(row.get("reasoning") or ""),  # kept for training; strip for UI demos
        "qwen25vl3b": scores["qwen25vl3b"],
        "llama32vl11b": scores["llama32vl11b"],
        "aya_vision_8b": scores["aya_vision_8b"],
        "composite_score": float(composite) if composite is not None else 0.0,
        "majority_accepted": bool(majority) if has_any else False,
        "affirmative_votes": int(votes) if has_any else 0,
        "dataset_accepted": bool(dataset_ok) if has_any else False,
        "source_dataset": source,
    }


def load_open_frames(include_flowchart: bool, allow_topup_sources: bool) -> pd.DataFrame:
    sources = list(OPEN_SOURCES)
    if include_flowchart:
        sources.extend(FLOWCHART_SOURCES)
    if allow_topup_sources:
        sources.extend(TOPUP_SOURCES)

    frames: list[pd.DataFrame] = []
    for meta in sorted(sources, key=lambda m: -m["priority"]):
        repo = meta["repo"]
        print(f"Loading {repo} ...")
        ds = load_dataset(repo, split="train")
        rows: list[dict[str, Any]] = []
        allow = meta.get("allow_types")
        for item in ds:
            code = str(item.get("uml_code") or "")
            inferred = infer_diagram_type(code)
            dtype = meta.get("forced_type") or inferred
            if allow is not None and dtype not in allow:
                continue
            if dtype == "unknown":
                continue
            if meta.get("forced_type") is None and inferred != dtype:
                continue
            # When forced_type is set, still skip obvious mismatches (e.g. usecase leaked into class repo)
            if meta.get("forced_type") and inferred not in {dtype, "unknown"} and inferred in {
                "usecase",
                "sequence",
                "state",
                "deployment",
            }:
                continue
            rows.append(normalize_row(dict(item), source=repo, diagram_type=dtype))
        df = pd.DataFrame(rows)
        print(f"  kept {len(df)} rows (types={dict(Counter(df['diagram_type']))})")
        frames.append(df)

    if not frames:
        raise RuntimeError("No open datasets loaded")
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["uml_code"], keep="first")
    return merged


def select_corpus(
    df: pd.DataFrame,
    *,
    target: int,
    per_type: int,
    seed: int,
    include_flowchart: bool,
) -> pd.DataFrame:
    rng = __import__("random").Random(seed)
    selected: list[pd.DataFrame] = []
    remaining_target = target

    types = list(PAPER_TYPES)
    if include_flowchart:
        types.append("flowchart")

    # First pass: fill each type up to per_type
    leftovers: dict[str, pd.DataFrame] = {}
    for dtype in types:
        pool = df[df["diagram_type"] == dtype].copy()
        idxs = list(pool.index)
        rng.shuffle(idxs)
        take_n = min(per_type, len(idxs), remaining_target)
        chosen = pool.loc[idxs[:take_n]]
        leftovers[dtype] = pool.loc[idxs[take_n:]]
        selected.append(chosen)
        remaining_target -= len(chosen)
        print(f"  {dtype}: selected {len(chosen)} (available {len(pool)})")

    # Second pass: top up to target, preferring class then other leftovers
    if remaining_target > 0:
        topup_order = ["class", "object", "component", "package"]
        if include_flowchart:
            topup_order.append("flowchart")
        for dtype in topup_order:
            if remaining_target <= 0:
                break
            pool = leftovers.get(dtype)
            if pool is None or pool.empty:
                continue
            idxs = list(pool.index)
            rng.shuffle(idxs)
            take_n = min(remaining_target, len(idxs))
            extra = pool.loc[idxs[:take_n]]
            selected.append(extra)
            remaining_target -= len(extra)
            print(f"  top-up {dtype}: +{len(extra)}")

    out = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    out = out.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    # Drop private reasoning from the public training export by default? Keep it —
    # training may want CoT; demos already strip. Document in manifest.
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ~8000 open-source UML training artifacts")
    parser.add_argument("--target", type=int, default=8000, help="Total rows to select")
    parser.add_argument("--per-type", type=int, default=2000, help="Preferred max per diagram type")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-flowchart",
        action="store_true",
        help="Exclude flowchart/activity rows (default includes them to reach 8000)",
    )
    parser.add_argument(
        "--include-flowchart",
        action="store_true",
        help="Accepted for compatibility; flowcharts are included by default unless --no-flowchart",
    )
    parser.add_argument(
        "--no-topup-sources",
        action="store_true",
        help="Do not use deployment/extra open repos for fill",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: data/training)",
    )
    args = parser.parse_args()
    include_flowchart = False if args.no_flowchart else True

    cfg = load_config()
    ensure_dirs(cfg)
    out_dir = args.out_dir or (Path(cfg["data_dir"]) / "training")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading / caching open Hugging Face UML sources …")
    pool = load_open_frames(
        include_flowchart=include_flowchart,
        allow_topup_sources=not args.no_topup_sources,
    )
    print(f"Deduped pool size: {len(pool)}")
    print("Pool by type:", dict(Counter(pool["diagram_type"])))

    corpus = select_corpus(
        pool,
        target=args.target,
        per_type=args.per_type,
        seed=args.seed,
        include_flowchart=include_flowchart,
    )
    if len(corpus) < args.target:
        print(
            f"WARNING: only {len(corpus)} unique open-source rows available "
            f"(requested {args.target})."
        )

    parquet_path = out_dir / "uml_training_8000.parquet"
    jsonl_path = out_dir / "uml_training_8000.jsonl"
    # Public training columns (keep reasoning for CoT fine-tuning)
    corpus.to_parquet(parquet_path, index=False)
    corpus.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

    by_type = corpus["diagram_type"].value_counts().to_dict()
    accepted = int(corpus["dataset_accepted"].sum()) if "dataset_accepted" in corpus else 0
    scored = int(corpus["qwen25vl3b"].notna().sum()) if "qwen25vl3b" in corpus else 0
    manifest = {
        "total_rows": len(corpus),
        "target": args.target,
        "per_type_preferred": args.per_type,
        "by_diagram_type": by_type,
        "scored_rows": scored,
        "dataset_accepted_rows": accepted,
        "seed": args.seed,
        "sources": [s["repo"] for s in OPEN_SOURCES]
        + ([s["repo"] for s in FLOWCHART_SOURCES] if include_flowchart else [])
        + ([] if args.no_topup_sources else [s["repo"] for s in TOPUP_SOURCES]),
        "outputs": {
            "parquet": str(parquet_path),
            "jsonl": str(jsonl_path),
        },
        "notes": [
            "Assembled from open Hugging Face UMLCode corpora (non-gated).",
            "Class rows are abundant; object/component/package open sets are ~1k each.",
            "Flowchart/activity (+ optional deployment-inferred types) fill remaining slots to hit 8000.",
            "Gated class scored repo (UMLCode-ClassDiagram-DeepSeek-32B-Scored) is not required.",
            "reasoning_private may contain model CoT; strip before UI display.",
        ],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nWrote {len(corpus)} artifacts → {parquet_path}")
    print(f"Wrote JSONL → {jsonl_path}")
    print(f"Manifest → {manifest_path}")
    print("By type:", by_type)


if __name__ == "__main__":
    main()
