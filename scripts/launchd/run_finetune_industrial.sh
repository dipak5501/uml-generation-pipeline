#!/usr/bin/env bash
# KeepAlive wrapper: complete industrial UML LoRA (does not touch live API adapter).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-industrial-complete}"
DATA="${DATA:-data/finetune_industrial}"
LOG="${LOG:-data/training/finetune_industrial_complete.log}"
WARM="${WARM_START:-models/uml-plantuml-lora-sourcecode-30k}"

mkdir -p "$ADAPTER" "$(dirname "$LOG")" "$DATA"

if [[ ! -f "$DATA/train.jsonl" ]]; then
  echo "==== $(date) building industrial complete corpus ====" | tee -a "$LOG"
  env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
    "$ROOT/.venv/bin/python" scripts/build_industrial_complete_uml_corpus.py >>"$LOG" 2>&1
  env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
    "$ROOT/.venv/bin/python" scripts/prepare_finetune_data.py \
      --input data/training/uml_industrial_complete.parquet \
      --out-dir "$DATA" \
      --max-spec-chars 2800 --max-uml-chars 3500 \
      --valid-ratio 0.04 --test-ratio 0.03 --prefer-accepted >>"$LOG" 2>&1
fi

if [[ ! -f "$ADAPTER/adapters.safetensors" ]] && [[ ! -f "$ADAPTER/0000100_adapters.safetensors" ]]; then
  if [[ -f "$WARM/adapters.safetensors" ]]; then
    cp "$WARM/adapters.safetensors" "$ADAPTER/adapters.safetensors"
    echo "Warm-start copied $WARM/adapters.safetensors → $ADAPTER" | tee -a "$LOG"
  fi
  if [[ -f "$WARM/adapter_config.json" && ! -f "$ADAPTER/adapter_config.json" ]]; then
    cp "$WARM/adapter_config.json" "$ADAPTER/adapter_config.json"
  fi
fi

export ADAPTER_PATH="$ADAPTER"
export DATA
# Continue past the finished batch=1 4000-iter run; LaunchAgent env can override.
export ITERS="${ITERS:-8000}"
export BATCH_SIZE="${BATCH_SIZE:-8}"
export MAX_SEQ="${MAX_SEQ:-2048}"
export SAVE_EVERY="${SAVE_EVERY:-100}"
export STEPS_EVAL="${STEPS_EVAL:-100}"
export LOG
exec bash "$ROOT/scripts/run_finetune_resilient.sh"
