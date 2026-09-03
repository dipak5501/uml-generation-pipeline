#!/usr/bin/env bash
# KeepAlive idle-aware supervisor: complete industrial UML LoRA.
# Does not touch live API adapter (sourcecode-30k). Continues past each pass
# when CONTINUOUS=1 by bumping ITERS and resuming from latest adapters.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=../idle_aware_train_lib.sh
source "$ROOT/scripts/idle_aware_train_lib.sh"

ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-industrial-complete}"
DATA="${DATA:-data/finetune_industrial}"
LOG="${LOG:-data/training/finetune_industrial_complete.log}"
WARM="${WARM_START:-models/uml-plantuml-lora-sourcecode-30k}"
PASS_ITERS="${PASS_ITERS:-4000}"
CONTINUOUS="${CONTINUOUS:-1}"
# Floor / ceiling for continuous targets
MIN_TARGET="${ITERS:-8000}"
MAX_TARGET="${MAX_ITERS:-100000}"

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
export LOG
export MAX_SEQ="${MAX_SEQ:-2048}"
export SAVE_EVERY="${SAVE_EVERY:-100}"
export STEPS_EVAL="${STEPS_EVAL:-100}"
export IDLE_MINUTES="${IDLE_MINUTES:-5}"
export BATCH_SIZE_IDLE="${BATCH_SIZE_IDLE:-8}"
export BATCH_SIZE_BUSY="${BATCH_SIZE_BUSY:-2}"
export UML_APP_DB="${UML_APP_DB:-data/uml_app.db}"
export TRAIN_NICE="${TRAIN_NICE:-10}"
export METAL_SLEEP="${METAL_SLEEP:-45}"
export BUSY_WAIT_SECS="${BUSY_WAIT_SECS:-60}"
export MAX_RESTARTS="${MAX_RESTARTS:-80}"

# Seed target from LaunchAgent env or default.
target="${MIN_TARGET}"

completed_now() {
  # Reuse resilient script's notion via a tiny inline call after exporting ADAPTER/LOG.
  ADAPTER_PATH="$ADAPTER" LOG="$LOG" bash -c '
    source "'"$ROOT"'/scripts/idle_aware_train_lib.sh"
    # Duplicate light progress probe (mtime-aware) without starting train.
    python3 - <<PY
import json, re
from pathlib import Path
adapter = Path("'"$ADAPTER"'")
log_path = Path("'"$LOG"'")
meta_iters = ckpt_iters = log_iters = 0
meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        d = json.loads(meta.read_text())
        meta_iters = int(d.get("iters_completed") or d.get("iters") or 0)
    except Exception:
        pass
meta_mtime = meta.stat().st_mtime if meta.is_file() else 0.0
numbered = []
for p in adapter.glob("*_adapters.safetensors"):
    head = p.name.split("_")[0]
    if head.isdigit():
        numbered.append((p.stat().st_mtime, int(head)))
if numbered:
    by_num = max(numbered, key=lambda t: t[1])
    by_mtime = max(numbered, key=lambda t: (t[0], t[1]))
    if by_mtime[1] >= meta_iters:
        ckpt_iters = by_mtime[1]
    elif by_num[1] >= meta_iters:
        ckpt_iters = by_num[1]
    elif by_mtime[0] > meta_mtime and meta_iters > 0:
        ckpt_iters = meta_iters + by_mtime[1]
    else:
        ckpt_iters = by_num[1]
if log_path.is_file():
    text = log_path.read_text(errors="replace")
    last = text.split("---- attempt ")[-1]
    prior = 0
    m = re.search(r"Prior iters=(\d+)", last)
    if m:
        prior = int(m.group(1))
    run_iters = [int(x) for x in re.findall(r"Iter (\d+): Train", last)]
    if run_iters:
        log_iters = prior + max(run_iters) if prior else max(run_iters)
print(max(meta_iters, ckpt_iters, log_iters))
PY
  '
}

echo "==== $(date) industrial idle-aware supervisor start continuous=$CONTINUOUS min_target=$target ====" | tee -a "$LOG"

pass=0
while true; do
  pass=$((pass + 1))
  done_iters="$(completed_now | tr -d '[:space:]')"
  done_iters="${done_iters:-0}"

  if [[ "$done_iters" -ge "$target" ]]; then
    if [[ "$CONTINUOUS" == "1" ]] && [[ "$target" -lt "$MAX_TARGET" ]]; then
      next=$((done_iters + PASS_ITERS))
      [[ "$next" -gt "$MAX_TARGET" ]] && next=$MAX_TARGET
      echo "Pass complete at $done_iters; bumping target $target → $next (continuous)" | tee -a "$LOG"
      target=$next
    else
      echo "Industrial training finished at $done_iters (target=$target continuous=$CONTINUOUS)" | tee -a "$LOG"
      echo "SWAP LATER (do not run until ready):" | tee -a "$LOG"
      echo "  # sed -i '' 's|^FINETUNED_ADAPTER_PATH=.*|FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-industrial-complete|' .env && bash scripts/restart_api.sh" | tee -a "$LOG"
      # Exit 0: with KeepAlive SuccessfulExit=false this stays down; with true KeepAlive it restarts.
      # Prefer sleep+continue when CONTINUOUS so launchd does not thrash.
      if [[ "$CONTINUOUS" == "1" ]]; then
        sleep 300
        continue
      fi
      exit 0
    fi
  fi

  # Idle batch for this pass; resilient script also re-checks per attempt.
  if uml_app_is_idle; then
    export BATCH_SIZE="${BATCH_SIZE_IDLE}"
    idle_state=idle
  else
    export BATCH_SIZE="${BATCH_SIZE_BUSY}"
    idle_state=busy
  fi
  export ITERS="$target"
  export BATCH_SIZE_IDLE BATCH_SIZE_BUSY

  echo "==== $(date) supervisor pass=$pass target=$target completed=$done_iters mode=$idle_state batch=$BATCH_SIZE ====" | tee -a "$LOG"

  set +e
  bash "$ROOT/scripts/run_finetune_resilient.sh"
  rc=$?
  set -e
  echo "supervisor pass=$pass resilient_exit=$rc completed=$(completed_now | tr -d '[:space:]')" | tee -a "$LOG"

  # Brief pause between passes; KeepAlive will also restart this script on crash.
  sleep 15
done
