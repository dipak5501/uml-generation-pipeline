# Fine-tuned PlantUML generator (MLX LoRA)

Adapters produced by:

```bash
pip install -r requirements-finetune.txt
python scripts/prepare_finetune_data.py   # needs data/training/uml_training_8000.parquet
python scripts/finetune_plantuml.py       # ~2000 LoRA iters on Apple Silicon
```

Outputs land in `models/uml-plantuml-lora/` (gitignored — large binary weights).

Enable in `.env`:

```bash
USE_FINETUNED_CODE=true
MOCK_PROVIDERS=true          # still OK — fine-tuned code model overrides only PlantUML generation
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
```

Spec generation and VLM scoring can remain mock/live independently; only the **code** stage uses the LoRA adapter when `USE_FINETUNED_CODE=true`.
