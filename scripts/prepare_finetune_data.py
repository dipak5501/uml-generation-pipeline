#!/usr/bin/env python3
"""
Convert data/training/uml_training_8000.parquet into MLX-LM LoRA JSONL splits.

Output directory (default data/finetune/):
  train.jsonl / valid.jsonl / test.jsonl

Each line:
  {"messages":[{"role":"system",...},{"role":"user",...},{"role":"assistant",...}]}
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd

SYSTEM = (
    "You are a UML expert. Given a technical specification and a target diagram type, "
    "output ONLY valid PlantUML between @startuml and @enduml. "
    "No markdown fences or commentary."
)


def _clean_uml(code: str) -> str:
    code = (code or "").strip()
    code = re.sub(r"^```(?:plantuml)?\s*", "", code, flags=re.I)
    code = re.sub(r"\s*```$", "", code)
    if "@startuml" not in code.lower():
        code = "@startuml\n" + code
    if "@enduml" not in code.lower():
        code = code.rstrip() + "\n@enduml"
    return code.strip()


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"


def row_to_messages(row: dict, max_spec: int, max_uml: int) -> dict | None:
    dtype = str(row.get("diagram_type") or "class").strip().lower()
    spec = str(row.get("technical_spec") or row.get("source_requirement") or "").strip()
    uml = _clean_uml(str(row.get("uml_code") or ""))
    if len(spec) < 40 or "@startuml" not in uml.lower():
        return None
    if len(uml) < 20:
        return None
    spec = _truncate(spec, max_spec)
    uml = _truncate(uml, max_uml)
    user = (
        f"Target diagram type: {dtype}\n\n"
        f"Technical specification:\n{spec}\n\n"
        f"Generate PlantUML for a {dtype} diagram."
    )
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": uml},
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/training/uml_training_8000.parquet"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/finetune"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-spec-chars", type=int, default=1800)
    parser.add_argument("--max-uml-chars", type=int, default=2500)
    parser.add_argument(
        "--prefer-accepted",
        action="store_true",
        help="If scored rows exist, put dataset_accepted rows first (still uses all valid rows).",
    )
    parser.add_argument("--valid-ratio", type=float, default=0.05)
    parser.add_argument("--test-ratio", type=float, default=0.05)
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(
            f"Missing {args.input}. Run: python scripts/build_training_corpus.py --target 8000"
        )

    df = pd.read_parquet(args.input)
    if args.prefer_accepted and "dataset_accepted" in df.columns:
        df = df.sort_values("dataset_accepted", ascending=False)

    records: list[dict] = []
    for row in df.to_dict(orient="records"):
        msg = row_to_messages(row, args.max_spec_chars, args.max_uml_chars)
        if msg:
            records.append(msg)

    rng = random.Random(args.seed)
    rng.shuffle(records)
    n = len(records)
    n_test = max(1, int(n * args.test_ratio))
    n_valid = max(1, int(n * args.valid_ratio))
    test = records[:n_test]
    valid = records[n_test : n_test + n_valid]
    train = records[n_test + n_valid :]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("valid", valid), ("test", test)):
        path = args.out_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} -> {path}")

    meta = {
        "source": str(args.input),
        "total_usable": n,
        "train": len(train),
        "valid": len(valid),
        "test": len(test),
        "max_spec_chars": args.max_spec_chars,
        "max_uml_chars": args.max_uml_chars,
        "seed": args.seed,
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
