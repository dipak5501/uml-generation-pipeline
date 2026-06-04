#!/usr/bin/env python3
"""Analyze VLM score distributions and export summary charts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from uml_pipeline.analyze import plot_score_distributions, summary_stats
from uml_pipeline.config import ensure_dirs, load_config
from uml_pipeline.datasets import load_merged

load_dotenv()


def main() -> None:
    cfg = load_config()
    ensure_dirs(cfg)
    df = load_merged(cfg)
    stats = summary_stats(df)
    print(json.dumps(stats, indent=2))

    fig_dir = Path(cfg["output_dir"]) / "figures"
    paths = plot_score_distributions(df, fig_dir)
    for p in paths:
        print(f"Saved {p}")


if __name__ == "__main__":
    main()
