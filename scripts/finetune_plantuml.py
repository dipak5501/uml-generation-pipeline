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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from latest checkpoint under adapter-path (e.g. 0000800_adapters.safetensors)",
    )
    parser.add_argument(
        "--resume-adapter-file",
        type=Path,
        default=None,
        help="Explicit adapter file to resume from",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test-set eval after training",
    )
    args = parser.parse_args()

    if args.quick:
        args.iters = min(args.iters, 200)
        args.save_every = 50
        args.steps_per_eval = 50

    if not args.skip_prepare or not (args.data / "train.jsonl").is_file():
        prep = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_finetune_data.py"),
                "--prefer-accepted",
            ],
            cwd=str(ROOT),
            check=False,
        )
        if prep.returncode != 0:
            raise SystemExit("Failed to prepare fine-tune data")

    train_path = args.data / "train.jsonl"
    if not train_path.is_file():
        raise SystemExit(f"Missing {train_path}")

    args.adapter_path.mkdir(parents=True, exist_ok=True)

    resume_file = args.resume_adapter_file
    if resume_file is None and args.resume:
        checkpoints = sorted(args.adapter_path.glob("*_adapters.safetensors"))
        if checkpoints:
            resume_file = checkpoints[-1]
            print(f"Resuming from {resume_file}")
        elif (args.adapter_path / "adapters.safetensors").is_file():
            resume_file = args.adapter_path / "adapters.safetensors"
            print(f"Resuming from {resume_file}")

    # If resuming a partial run, train remaining iters toward the requested total when meta exists
    prior_iters = 0
    meta_path = args.adapter_path / "finetune_meta.json"
    if resume_file:
        ckpt_name = Path(resume_file).name
        if ckpt_name.startswith("000") and "_adapters" in ckpt_name:
            try:
                prior_iters = max(prior_iters, int(ckpt_name.split("_")[0]))
            except ValueError:
                pass
        if meta_path.is_file():
            try:
                prior = json.loads(meta_path.read_text(encoding="utf-8"))
                prior_iters = max(
                    prior_iters,
                    int(prior.get("iters_completed") or prior.get("iters") or 0),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        # When --resume and prior < requested, run the remaining steps
        if prior_iters and prior_iters < args.iters and not args.quick:
            remaining = args.iters - prior_iters
            print(f"Prior iters={prior_iters}; continuing for {remaining} more (target {args.iters})")
            args.iters = remaining

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
    if resume_file:
        cmd.extend(["--resume-adapter-file", str(resume_file)])
    if args.test:
        cmd.append("--test")
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    completed = prior_iters + args.iters if resume_file and prior_iters else args.iters
    meta = {
        "base_model": args.model,
        "adapter_path": str(args.adapter_path),
        "iters": completed,
        "iters_completed": completed,
        "iters_this_run": args.iters,
        "resumed_from": str(resume_file) if resume_file else None,
        "stopped_early": False,
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
    print("  MOCK_PROVIDERS=true")
    print("  USE_FINETUNED_CODE=true")
    print(f"  FINETUNED_ADAPTER_PATH={args.adapter_path}")
    print(f"  FINETUNED_BASE_MODEL={args.model}")


if __name__ == "__main__":
    main()
