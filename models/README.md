# Fine-tuned PlantUML generator (MLX LoRA on **real** Hugging Face UML data)

## What “real data” means here

Training rows come from open Hugging Face **UMLCode** corpora (requirements/specs + PlantUML),
assembled locally as:

| File | Role |
|------|------|
| `data/training/uml_training_8000.parquet` | ~8k class/object/component/package/flowchart |
| `data/training/uml_training_supplement_merged.parquet` | 10k = 8k + scenario/code supplements |
| `data/finetune/{train,valid,test}.jsonl` | Chat-format pairs for MLX LoRA |

Sources (see `data/training/manifest.json`): nguyenvanviet UMLCode class/object/component/package scored + activity sets.

## Train (Apple Silicon)

```bash
pip install -r requirements-finetune.txt

# One-shot: prepare JSONL from merged real corpus + continue LoRA
make train-real

# Or step-by-step:
make finetune-prepare   # uses uml_training_supplement_merged.parquet
make finetune           # resume toward 2000+ iters
```

Adapters land in `models/uml-plantuml-lora/` (gitignored).

## Enable in the running app

`.env`:

```bash
USE_FINETUNED_CODE=true
MOCK_PROVIDERS=false          # or true — LoRA still used for PlantUML when fine-tune is on
USE_OLLAMA=true               # Stage-1 spec + VLM can stay local
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
FINETUNED_MAX_TOKENS=512
```

Restart:

```bash
./scripts/run_local.sh
```

Only the **PlantUML code** stage uses the LoRA adapter. Spec + VLM scoring use mock/Ollama/HF independently.

When `USE_FINETUNED_CODE=true`, generation **prefers LoRA** for class/object/component/package/flowchart, then falls back to the grounded spec-builder if the model output fails validation or fidelity checks.
