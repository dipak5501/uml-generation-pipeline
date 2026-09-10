#!/usr/bin/env bash
# Unattended UML-in-the-Wild: convert → prepare JSONL → LoRA into NEW adapter
# models/uml-plantuml-lora-wild. Does NOT change live FINETUNED_ADAPTER_PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${LOG:-$ROOT/data/training/finetune_wild.log}"
CHAIN_LOG="${CHAIN_LOG:-$ROOT/data/training/wild_train_chain.log}"
ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-wild}"
DATA="${DATA:-data/finetune_wild}"
ITERS="${ITERS:-18000}"
WARM="${WARM_START:-models/uml-plantuml-lora-sourcecode-30k}"
PARQUET_APP="data/training/uml_in_the_wild_app.parquet"
PIDFILE="$ROOT/data/training/wild_train_chain.pid"

mkdir -p "$(dirname "$LOG")" "$ADAPTER" "$DATA" data/training data/raw/uml_in_the_wild
echo $$ >"$PIDFILE"

exec >>"$CHAIN_LOG" 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Keep awake for this chain (LaunchAgent caffeinate should also be running).
if ! pgrep -x caffeinate >/dev/null 2>&1; then
  /usr/bin/caffeinate -dimsu &
  log "Started nested caffeinate pid=$!"
fi

log "==== Wild chain START pid=$$ adapter=$ADAPTER iters=$ITERS ===="
log "Live .env adapter MUST stay sourcecode-30k (this script never edits .env)."

# Pause industrial if somehow still loaded (best-effort; may already be bootout).
UID_NUM="$(id -u)"
if launchctl print "gui/${UID_NUM}/com.uml.pipeline.finetune-industrial" >/dev/null 2>&1; then
  log "Booting out industrial LaunchAgent for GPU exclusivity…"
  launchctl bootout "gui/${UID_NUM}/com.uml.pipeline.finetune-industrial" 2>/dev/null || true
  pkill -f 'uml-plantuml-lora-industrial' 2>/dev/null || true
fi

# Ensure raw assets (metadata + puml zip). Skip 4.3GB PNG archive.
RAW="$ROOT/data/raw/uml_in_the_wild"
BASE="https://zenodo.org/api/records/18952372/files"
download() {
  local key="$1" dest="$2"
  if [[ -f "$dest" && -s "$dest" ]]; then
    log "OK exists: $dest ($(du -h "$dest" | awk '{print $1}'))"
    return 0
  fi
  log "Downloading $key → $dest"
  curl -L --fail --retry 8 --retry-delay 15 -C - --connect-timeout 30 \
    -o "${dest}.partial" "${BASE}/${key}/content"
  mv -f "${dest}.partial" "$dest"
  log "Downloaded $dest"
}

download "uml_metadata_enriched.json" "$RAW/uml_metadata_enriched.json"
download "puml_files.zip" "$RAW/puml_files.zip"
[[ -f "$RAW/README.md" ]] || download "README.md" "$RAW/README.md" || true

# Convert
log "=== import_uml_in_the_wild.py ==="
env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" "$ROOT/scripts/import_uml_in_the_wild.py" \
  --raw-dir "$RAW" \
  --out data/training/uml_in_the_wild.parquet \
  --out-app "$PARQUET_APP"

if [[ ! -f "$PARQUET_APP" ]]; then
  log "FATAL: missing $PARQUET_APP"
  exit 1
fi

# Prepare finetune JSONL (dedicated dir — do not clobber data/finetune/)
log "=== prepare_finetune_data → $DATA ==="
env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" "$ROOT/scripts/prepare_finetune_data.py" \
  --input "$PARQUET_APP" \
  --out-dir "$DATA" \
  --prefer-accepted \
  --valid-ratio 0.02 \
  --test-ratio 0.02 \
  --max-spec-chars 1800 \
  --max-uml-chars 2500

# Warm-start from production adapter (copy once if no wild adapters yet)
if [[ ! -f "$ADAPTER/adapters.safetensors" ]] && [[ ! -f "$ADAPTER/0000100_adapters.safetensors" ]]; then
  if [[ -f "$WARM/adapters.safetensors" ]]; then
    cp "$WARM/adapters.safetensors" "$ADAPTER/adapters.safetensors"
    [[ -f "$WARM/adapter_config.json" ]] && cp "$WARM/adapter_config.json" "$ADAPTER/adapter_config.json"
    log "Warm-start copied $WARM → $ADAPTER"
  fi
fi

log "=== resilient LoRA train iters=$ITERS log=$LOG ==="
ADAPTER_PATH="$ADAPTER" \
  DATA="$DATA" \
  ITERS="$ITERS" \
  BATCH_SIZE=2 \
  BATCH_SIZE_IDLE=2 \
  BATCH_SIZE_BUSY=2 \
  MAX_SEQ=1536 \
  SAVE_EVERY=200 \
  STEPS_EVAL=200 \
  LOG="$LOG" \
  bash "$ROOT/scripts/run_finetune_resilient.sh"

log "==== Wild chain COMPLETE adapter=$ADAPTER ===="
log "NOT LIVE — eval then manually set FINETUNED_ADAPTER_PATH=$ADAPTER and restart_api.sh"
rm -f "$PIDFILE"
