#!/usr/bin/env python3
"""
Run the 3-stage generation pipeline (spec -> PlantUML -> VLM validation).

Requires API keys or Ollama with vision models. To use pre-built benchmark data:
python scripts/download_datasets.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from uml_pipeline.config import ensure_dirs, load_config
from uml_pipeline.pipeline import run_generation_batch, save_batch

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diagram-type",
        required=True,
        choices=["class", "object", "component", "package", "flowchart"],
    )
    parser.add_argument("-n", "--num-samples", type=int, default=5)
    parser.add_argument(
        "--spec-mode",
        choices=["architect", "user"],
        default="architect",
        help="architect = technical spec; user = end-user feature description",
    )
    args = parser.parse_args()

    cfg = load_config()
    ensure_dirs(cfg)

    print(
        "Generation uses LLM/VLM APIs. Set OPENAI_API_KEY or USE_OLLAMA=true.\n"
        f"Spec model: {__import__('os').environ.get('SPEC_MODEL', 'llama3.2:1b')}\n"
        f"Code model: {__import__('os').environ.get('CODE_MODEL', 'deepseek-r1:32b')}"
    )

    df = run_generation_batch(
        cfg, args.diagram_type, args.num_samples, spec_mode=args.spec_mode
    )
    out = save_batch(df, cfg, args.diagram_type)
    print(f"Saved {len(df)} samples to {out}")


if __name__ == "__main__":
    main()
