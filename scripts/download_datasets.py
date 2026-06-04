#!/usr/bin/env python3
"""Download optional Hugging Face UML benchmark datasets and merge them."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from uml_pipeline.config import ensure_dirs, load_config
from uml_pipeline.datasets import download_all

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download UML benchmark datasets from Hugging Face")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max rows per diagram type (default: all available)",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["class", "object", "component", "package"],
        help="Download specific diagram types only",
    )
    parser.add_argument(
        "--skip-errors",
        action="store_true",
        help="Continue if a dataset is gated or unavailable",
    )
    args = parser.parse_args()

    cfg = load_config()
    ensure_dirs(cfg)
    download_all(
        cfg,
        limit_per_type=args.limit,
        only_types=args.only,
        skip_errors=args.skip_errors,
    )


if __name__ == "__main__":
    main()
