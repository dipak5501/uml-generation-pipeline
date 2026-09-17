#!/usr/bin/env bash
# Merge all usable training corpora → prepare JSONL → LoRA into NEW adapter
# models/uml-plantuml-lora-all. Does NOT change live FINETUNED_ADAPTER_PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${LOG:-$ROOT/data/training/finetune_all.log}"
CHAIN_LOG="${CHAIN_LOG:-$ROOT/data/training/all_corpora_train_chain.log}"
ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-all}"
DATA="${DATA:-data/finetune_all}"
ITERS="${ITERS:-25000}"
# Prefer wild (18k completed) over sourcecode-30k (6k) as warm-start; override with WARM_START=.
WARM="${WARM_START:-models/uml-plantuml-lora-wild}"
PARQUET="data/training/uml_training_all_merged.parquet"
PIDFILE="$ROOT/data/training/all_corpora_train_chain.pid"

mkdir -p "$(dirname "$LOG")" "$ADAPTER" "$DATA" data/training
echo $$ >"$PIDFILE"

exec >>"$CHAIN_LOG" 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if ! pgrep -x caffeinate >/dev/null 2>&1; then
  /usr/bin/caffeinate -dimsu &
  log "Started nested caffeinate pid=$!"
fi

log "==== All-corpora chain START pid=$$ adapter=$ADAPTER iters=$ITERS ===="
log "Live .env adapter MUST stay sourcecode-30k (this script never edits .env)."

UID_NUM="$(id -u)"
# Pause Metal-contending train agents (best-effort).
for agent in com.uml.pipeline.finetune-industrial com.uml.pipeline.self-train; do
  if launchctl print "gui/${UID_NUM}/${agent}" >/dev/null 2>&1; then
    log "Booting out ${agent} for GPU exclusivity…"
    launchctl bootout "gui/${UID_NUM}/${agent}" 2>/dev/null || true
  fi
done
pkill -f 'uml-plantuml-lora-industrial|uml-plantuml-lora-adaptation|run_self_training_loop' 2>/dev/null || true

log "=== merge_all_training_corpora.py ==="
env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" "$ROOT/scripts/merge_all_training_corpora.py"

if [[ ! -f "$PARQUET" ]]; then
  log "FATAL: missing $PARQUET"
  exit 1
fi

log "=== prepare_finetune_data → $DATA ==="
env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" "$ROOT/scripts/prepare_finetune_data.py" \
  --input "$PARQUET" \
  --out-dir "$DATA" \
  --prefer-accepted \
  --valid-ratio 0.02 \
  --test-ratio 0.02 \
  --max-spec-chars 1800 \
  --max-uml-chars 2500

# Warm-start once if no all-adapter weights yet
if [[ ! -f "$ADAPTER/adapters.safetensors" ]] && [[ ! -f "$ADAPTER/0000100_adapters.safetensors" ]]; then
  if [[ -f "$WARM/adapters.safetensors" ]]; then
    cp "$WARM/adapters.safetensors" "$ADAPTER/adapters.safetensors"
    [[ -f "$WARM/adapter_config.json" ]] && cp "$WARM/adapter_config.json" "$ADAPTER/adapter_config.json"
    log "Warm-start copied $WARM → $ADAPTER"
  elif [[ -f "models/uml-plantuml-lora-sourcecode-30k/adapters.safetensors" ]]; then
    cp models/uml-plantuml-lora-sourcecode-30k/adapters.safetensors "$ADAPTER/adapters.safetensors"
    [[ -f models/uml-plantuml-lora-sourcecode-30k/adapter_config.json ]] && \
      cp models/uml-plantuml-lora-sourcecode-30k/adapter_config.json "$ADAPTER/adapter_config.json"
    log "Warm-start fallback: sourcecode-30k → $ADAPTER"
  fi
fi

log "=== resilient LoRA train iters=$ITERS log=$LOG ==="
ADAPTER_PATH="$ADAPTER" \
  DATA="$DATA" \
  ITERS="$ITERS" \
  BATCH_SIZE=2 \
  BATCH_SIZE_IDLE=2 \
  BATCH_SIZE_BUSY=1 \
  MAX_SEQ=1536 \
  SAVE_EVERY=200 \
  STEPS_EVAL=200 \
  LOG="$LOG" \
  bash "$ROOT/scripts/run_finetune_resilient.sh"

log "==== All-corpora chain COMPLETE adapter=$ADAPTER ===="
log "NOT LIVE — eval then: bash scripts/switch_live_adapter.sh models/uml-plantuml-lora-all"
log "Or: sed FINETUNED_ADAPTER_PATH + bash scripts/restart_api.sh"
rm -f "$PIDFILE"
