#!/usr/bin/env python3
"""Render PlantUML from downloaded dataset to PNG images."""

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from uml_pipeline.config import ensure_dirs, load_config
from uml_pipeline.datasets import load_merged
from uml_pipeline.render import render_plantuml

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Max diagrams to render")
    parser.add_argument("--diagram-type", choices=["class", "object", "component", "package"])
    args = parser.parse_args()

    cfg = load_config()
    ensure_dirs(cfg)
    df = load_merged(cfg)

    if args.diagram_type:
        df = df[df["diagram_type"] == args.diagram_type]
    df = df.head(args.limit)

    jar = Path(cfg["root"]) / cfg["plantuml"]["jar_path"]
    img_root = Path(cfg["data_dir"]) / "images"

    ok, fail = 0, 0
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="render"):
        out_dir = img_root / str(row["diagram_type"])
        path, err = render_plantuml(str(row["uml_code"]), out_dir, jar)
        if path:
            ok += 1
        else:
            fail += 1
            if fail <= 3:
                print(f"  fail row {idx}: {err}")

    print(f"Done: {ok} rendered, {fail} failed")


if __name__ == "__main__":
    main()
