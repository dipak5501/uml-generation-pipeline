#!/usr/bin/env python3
"""
Fine-tune a small instruct model on the 8k UML→PlantUML corpus with MLX-LM LoRA (Apple Silicon).

Prereqs:
  pip install -r requirements-finetune.txt
  python scripts/prepare_finetune_data.py

Example (full 8k-oriented run on M2):
  python scripts/finetune_plantuml.py

Quick smoke (fewer iters):
  python scripts/finetune_plantuml.py --iters 200 --quick
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA fine-tune PlantUML generator (MLX)")
    parser.add_argument(
        "--model",
        default="mlx-community/Qwen2.5-0.5B-Instruct-4bit",
        help="Base MLX / HF model id",
    )
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "finetune")
    parser.add_argument(
        "--adapter-path",
        type=Path,
        default=ROOT / "models" / "uml-plantuml-lora",
    )
    parser.add_argument("--iters", type=int, default=2000, help="Training iterations")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--num-layers", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--save-every", type=int, default=200)
    parser.add_argument("--steps-per-eval", type=int, default=100)
    parser.add_argument("--steps-per-report", type=int, default=20)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Override to a short run (200 iters) for pipeline validation",
    )
    parser.add_argument("--skip-prepare", action="store_true")
    args = parser.parse_args()

    if args.quick:
        args.iters = min(args.iters, 200)
        args.save_every = 50
        args.steps_per_eval = 50

    if not args.skip_prepare or not (args.data / "train.jsonl").is_file():
        prep = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "prepare_finetune_data.py")],
            cwd=str(ROOT),
            check=False,
        )
        if prep.returncode != 0:
            raise SystemExit("Failed to prepare fine-tune data")

    train_path = args.data / "train.jsonl"
    if not train_path.is_file():
        raise SystemExit(f"Missing {train_path}")

    args.adapter_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "mlx_lm",
        "lora",
        "--model",
        args.model,
        "--train",
        "--data",
        str(args.data),
        "--fine-tune-type",
        "lora",
        "--mask-prompt",
        "--batch-size",
        str(args.batch_size),
        "--iters",
        str(args.iters),
        "--learning-rate",
        str(args.learning_rate),
        "--num-layers",
        str(args.num_layers),
        "--max-seq-length",
        str(args.max_seq_length),
        "--adapter-path",
        str(args.adapter_path),
        "--save-every",
        str(args.save_every),
        "--steps-per-eval",
        str(args.steps_per_eval),
        "--steps-per-report",
        str(args.steps_per_report),
        "--grad-checkpoint",
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    meta = {
        "base_model": args.model,
        "adapter_path": str(args.adapter_path),
        "iters": args.iters,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "num_layers": args.num_layers,
        "max_seq_length": args.max_seq_length,
        "data": str(args.data),
        "task": "specification_to_plantuml",
    }
    (args.adapter_path / "finetune_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"\nFine-tune complete. Adapters → {args.adapter_path}")
    print("Enable in app:")
    print("  MOCK_PROVIDERS=false")
    print("  USE_FINETUNED_CODE=true")
    print(f"  FINETUNED_ADAPTER_PATH={args.adapter_path}")
    print(f"  FINETUNED_BASE_MODEL={args.model}")


if __name__ == "__main__":
    main()
