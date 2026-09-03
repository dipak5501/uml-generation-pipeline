#!/usr/bin/env python3
"""Build a self-training mix: live accepted top-up + on-disk corpora → finetune JSONL.

Sources (all optional; uses whatever exists):
  - data/training/uml_accepted_live_topup.parquet   (harvest)
  - data/training/uml_industrial_complete.parquet
  - data/training/uml_source_code_30k_jpc.parquet / combined sourcecode 30k
  - data/training/scenarios_*.jsonl (eval scenarios, if present)

Writes parquet + prepares MLX chat JSONL under data/finetune_adaptation/.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.settings import ROOT

COLS = [
    "diagram_type",
    "input_mode",
    "source_language",
    "source_requirement",
    "technical_spec",
    "uml_code",
    "dataset_accepted",
    "majority_accepted",
    "scores",
    "source_dataset",
]


def _normalize(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLS)
    out = df.copy()
    rename = {}
    if "uml_code" not in out.columns and "plantuml_code" in out.columns:
        rename["plantuml_code"] = "uml_code"
    if rename:
        out = out.rename(columns=rename)
    for c in COLS:
        if c not in out.columns:
            if c in {"dataset_accepted", "majority_accepted"}:
                out[c] = True
            elif c == "scores":
                out[c] = 0.0
            elif c == "input_mode":
                out[c] = "requirement"
            elif c == "source_dataset":
                out[c] = source
            else:
                out[c] = None
    out["source_dataset"] = out["source_dataset"].fillna(source)
    out["dataset_accepted"] = out["dataset_accepted"].fillna(False).astype(bool)
    return out[COLS]


def _load_parquet(path: Path, source: str, max_rows: int | None, rng: random.Random) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=COLS)
    df = pd.read_parquet(path)
    df = _normalize(df, source)
    if max_rows is not None and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=rng.randint(1, 10_000_000))
    return df.reset_index(drop=True)


def _load_scenarios_jsonl(path: Path, max_rows: int, rng: random.Random) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=COLS)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            spec = str(rec.get("technical_spec") or rec.get("requirement") or "").strip()
            uml = str(rec.get("uml_code") or rec.get("plantuml") or "").strip()
            if len(spec) < 40 or "@startuml" not in uml.lower():
                continue
            rows.append(
                {
                    "diagram_type": str(rec.get("diagram_type") or "class").lower(),
                    "input_mode": str(rec.get("input_mode") or "requirement").lower(),
                    "source_language": rec.get("source_language"),
                    "source_requirement": rec.get("source_requirement") or "",
                    "technical_spec": spec,
                    "uml_code": uml,
                    "dataset_accepted": True,
                    "majority_accepted": True,
                    "scores": float(rec.get("scores") or 0.0),
                    "source_dataset": "eval_scenarios",
                }
            )
    if not rows:
        return pd.DataFrame(columns=COLS)
    if len(rows) > max_rows:
        rows = rng.sample(rows, max_rows)
    return pd.DataFrame(rows)[COLS]


def build_mix(
    *,
    harvest_path: Path,
    industrial_path: Path,
    source30k_path: Path,
    scenarios_path: Path,
    industrial_sample: int,
    source_sample: int,
    scenario_sample: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rng = random.Random(seed)
    parts: list[pd.DataFrame] = []
    sources: dict[str, int] = {}

    harvest_raw = (
        pd.read_parquet(harvest_path) if harvest_path.is_file() else pd.DataFrame()
    )
    harvest = _normalize(harvest_raw, "live_accepted_harvest") if len(harvest_raw) else pd.DataFrame(columns=COLS)
    if len(harvest):
        boost = harvest
        if "human_reviewed" in harvest_raw.columns:
            human = harvest_raw[harvest_raw["human_reviewed"] == True]  # noqa: E712
            if len(human):
                boost = pd.concat(
                    [boost, _normalize(human, "live_human_boost")], ignore_index=True
                )
        hq = harvest[harvest["scores"].fillna(0) >= 4.0]
        if len(hq):
            boost = pd.concat([boost, hq], ignore_index=True)
        parts.append(boost)
        sources["live_accepted"] = int(len(harvest))
        sources["live_after_boost"] = int(len(boost))

    ind = _load_parquet(industrial_path, "industrial_complete", industrial_sample, rng)
    if len(ind):
        parts.append(ind)
        sources["industrial_sample"] = len(ind)

    src = _load_parquet(source30k_path, "sourcecode_30k", source_sample, rng)
    if len(src):
        parts.append(src)
        sources["sourcecode_sample"] = len(src)

    scen = _load_scenarios_jsonl(scenarios_path, scenario_sample, rng)
    if len(scen):
        parts.append(scen)
        sources["scenarios_sample"] = len(scen)

    if not parts:
        mix = pd.DataFrame(columns=COLS)
    else:
        mix = pd.concat(parts, ignore_index=True)
        # Drop empty UML / short specs
        mix = mix[
            mix["technical_spec"].astype(str).str.len().ge(40)
            & mix["uml_code"].astype(str).str.contains("@startuml", case=False, na=False)
        ].reset_index(drop=True)

    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(mix)),
        "sources": sources,
        "seed": seed,
    }
    return mix, meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--harvest",
        type=Path,
        default=ROOT / "data" / "training" / "uml_accepted_live_topup.parquet",
    )
    parser.add_argument(
        "--industrial",
        type=Path,
        default=ROOT / "data" / "training" / "uml_industrial_complete.parquet",
    )
    parser.add_argument(
        "--source30k",
        type=Path,
        default=ROOT / "data" / "training" / "uml_source_code_30k_jpc.parquet",
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=ROOT / "data" / "training" / "scenarios_1000.jsonl",
    )
    parser.add_argument("--industrial-sample", type=int, default=4000)
    parser.add_argument("--source-sample", type=int, default=3000)
    parser.add_argument("--scenario-sample", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out-parquet",
        type=Path,
        default=ROOT / "data" / "training" / "uml_adaptation_mix.parquet",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "finetune_adaptation",
    )
    parser.add_argument("--skip-prepare", action="store_true")
    args = parser.parse_args()

    # Prefer combined sourcecode corpus if the focused 30k parquet is missing.
    source_path = args.source30k
    if not source_path.is_file():
        alt = ROOT / "data" / "training" / "uml_training_combined_sourcecode_30k.parquet"
        if alt.is_file():
            source_path = alt

    mix, meta = build_mix(
        harvest_path=args.harvest,
        industrial_path=args.industrial,
        source30k_path=source_path,
        scenarios_path=args.scenarios,
        industrial_sample=args.industrial_sample,
        source_sample=args.source_sample,
        scenario_sample=args.scenario_sample,
        seed=args.seed,
    )
    args.out_parquet.parent.mkdir(parents=True, exist_ok=True)
    mix.to_parquet(args.out_parquet, index=False)
    meta["parquet"] = str(args.out_parquet)
    meta_path = args.out_parquet.with_name("adaptation_mix_manifest.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))

    if args.skip_prepare:
        return
    if len(mix) < 8:
        print("Mix too small for prepare_finetune_data; skipping JSONL.", file=sys.stderr)
        return

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "prepare_finetune_data.py"),
        "--input",
        str(args.out_parquet),
        "--out-dir",
        str(args.out_dir),
        "--prefer-accepted",
        "--valid-ratio",
        "0.05",
        "--test-ratio",
        "0.05",
        "--max-spec-chars",
        "2200",
        "--max-uml-chars",
        "3000",
    ]
    subprocess.check_call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    main()
