#!/usr/bin/env python3
"""
Fine-tune Qwen2.5-0.5B-Instruct on the UML→PlantUML JSONL corpus with PEFT LoRA (NVIDIA CUDA).

Do not use mlx_lm on NVIDIA. Apple Silicon should keep using scripts/finetune_plantuml.py.

Prereqs:
  pip install -r requirements-finetune-cuda.txt
  python scripts/prepare_finetune_data.py

Example:
  python scripts/finetune_plantuml_cuda.py --iters 3000
  python scripts/finetune_plantuml_cuda.py --quick
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _require_cuda() -> None:
    try:
        import torch
    except ImportError as exc:
        raise SystemExit(
            "PyTorch is not installed. On NVIDIA: pip install -r requirements-finetune-cuda.txt"
        ) from exc
    if not torch.cuda.is_available():
        raise SystemExit(
            "No CUDA GPU detected. This script is NVIDIA-only. "
            "On Apple Silicon run: python scripts/finetune_plantuml.py"
        )


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"No rows in {path}")
    return rows


def _tokenize_rows(rows: list[dict], tokenizer, max_seq_length: int):
    import torch
    from torch.utils.data import Dataset

    class ChatSftDataset(Dataset):
        def __init__(self, examples: list[dict]):
            self.examples = examples

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, idx: int) -> dict:
            return self.examples[idx]

    encoded: list[dict] = []
    for row in rows:
        messages = row.get("messages") or []
        if len(messages) < 2:
            continue
        prompt_messages = messages[:-1]
        if hasattr(tokenizer, "apply_chat_template"):
            prompt = tokenizer.apply_chat_template(
                prompt_messages, tokenize=False, add_generation_prompt=True
            )
            full = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
        else:
            prompt = ""
            for msg in prompt_messages:
                prompt += f"{msg.get('role', 'user')}: {msg.get('content', '')}\n"
            prompt += "assistant: "
            full = prompt + str(messages[-1].get("content") or "")
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
        if len(full_ids) > max_seq_length:
            full_ids = full_ids[:max_seq_length]
        labels = list(full_ids)
        prompt_len = min(len(prompt_ids), len(labels))
        labels[:prompt_len] = [-100] * prompt_len
        encoded.append(
            {
                "input_ids": torch.tensor(full_ids, dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long),
                "attention_mask": torch.ones(len(full_ids), dtype=torch.long),
            }
        )
    if not encoded:
        raise SystemExit("No tokenized training examples")
    return ChatSftDataset(encoded)


def _collate(features: list[dict], pad_id: int):
    import torch

    max_len = max(int(f["input_ids"].shape[0]) for f in features)
    input_ids, labels, mask = [], [], []
    for feat in features:
        pad = max_len - int(feat["input_ids"].shape[0])
        input_ids.append(
            torch.nn.functional.pad(feat["input_ids"], (0, pad), value=pad_id)
        )
        labels.append(torch.nn.functional.pad(feat["labels"], (0, pad), value=-100))
        mask.append(torch.nn.functional.pad(feat["attention_mask"], (0, pad), value=0))
    return {
        "input_ids": torch.stack(input_ids),
        "labels": torch.stack(labels),
        "attention_mask": torch.stack(mask),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA fine-tune PlantUML generator (CUDA PEFT)")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Hugging Face base model (not mlx-community)",
    )
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "finetune")
    parser.add_argument(
        "--adapter-path",
        type=Path,
        default=ROOT / "models" / "uml-plantuml-lora",
    )
    parser.add_argument("--iters", type=int, default=2000, help="Trainer max_steps")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--save-every", type=int, default=200)
    parser.add_argument("--logging-steps", type=int, default=20)
    parser.add_argument("--quick", action="store_true", help="Short run to validate the pipeline")
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Continue from existing adapter-path")
    args = parser.parse_args()

    if "mlx-community" in args.model.lower() or "mlx_lm" in args.model.lower():
        raise SystemExit("Do not pass an MLX model id to the CUDA trainer. Use Qwen/Qwen2.5-0.5B-Instruct.")

    _require_cuda()

    if args.quick:
        args.iters = min(args.iters, 50)
        args.save_every = 25

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

    import torch
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_ds = _tokenize_rows(_load_jsonl(train_path), tokenizer, args.max_seq_length)
    valid_path = args.data / "valid.jsonl"
    eval_ds = (
        _tokenize_rows(_load_jsonl(valid_path), tokenizer, args.max_seq_length)
        if valid_path.is_file()
        else None
    )

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    if args.resume and (args.adapter_path / "adapter_config.json").is_file():
        print(f"Resuming PEFT adapters from {args.adapter_path}")
        model = PeftModel.from_pretrained(model, str(args.adapter_path), is_trainable=True)
    else:
        lora = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            bias="none",
        )
        model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    args.adapter_path.mkdir(parents=True, exist_ok=True)
    targs = TrainingArguments(
        output_dir=str(args.adapter_path / "trainer"),
        max_steps=args.iters,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        logging_steps=args.logging_steps,
        save_steps=args.save_every,
        save_total_limit=3,
        fp16=True,
        bf16=False,
        eval_strategy="steps" if eval_ds is not None else "no",
        eval_steps=args.save_every if eval_ds is not None else None,
        report_to=[],
        remove_unused_columns=False,
        dataloader_pin_memory=True,
        gradient_checkpointing=True,
    )

    def collate(features: list[dict]) -> dict:
        return _collate(features, tokenizer.pad_token_id or tokenizer.eos_token_id)

    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collate,
    )
    trainer.train()
    model.save_pretrained(str(args.adapter_path))
    tokenizer.save_pretrained(str(args.adapter_path))

    meta = {
        "backend": "peft-cuda",
        "base_model": args.model,
        "adapter_path": str(args.adapter_path),
        "iters": args.iters,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "max_seq_length": args.max_seq_length,
        "data": str(args.data),
        "task": "specification_to_plantuml",
    }
    (args.adapter_path / "finetune_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"\nCUDA LoRA complete. Adapters → {args.adapter_path}")
    print("Enable in .env:")
    print("  USE_FINETUNED_CODE=true")
    print(f"  FINETUNED_ADAPTER_PATH={args.adapter_path}")
    print(f"  FINETUNED_BASE_MODEL={args.model}")


if __name__ == "__main__":
    main()
