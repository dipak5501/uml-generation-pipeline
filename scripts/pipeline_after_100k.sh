#!/usr/bin/env bash
# Autonomous supervisor: wait for 100k LoRA → deploy → collect 200k corpus → train 200k.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${ROOT}/data/training/pipeline_after_100k.log"
TARGET_ITERS=18000
ADAPTER_100K="${ROOT}/models/uml-plantuml-lora-100k"
ADAPTER_200K="${ROOT}/models/uml-plantuml-lora-200k"
VAL_50K=1.229

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

best_val_loss() {
  python3 - <<'PY'
import re
from pathlib import Path
log = Path("data/training/finetune_100k.log")
if not log.is_file():
    print("999")
    raise SystemExit
vals = [float(m.group(1)) for m in re.finditer(r"Iter \d+: Val loss ([0-9.]+)", log.read_text())]
print(f"{min(vals):.4f}" if vals else "999")
PY
}

completed_iters() {
  python3 - <<PY
import json
from pathlib import Path
adapter = Path("$ADAPTER_100K")
meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        d = json.loads(meta.read_text())
        print(int(d.get("iters_completed") or d.get("iters") or 0))
        raise SystemExit
    except Exception:
        pass
ckpts = sorted(adapter.glob("*_adapters.safetensors"))
print(int(ckpts[-1].name.split("_")[0]) if ckpts else 0)
PY
}

wait_for_100k() {
  log "Waiting for 100k LoRA training ($TARGET_ITERS iters) …"
  while true; done="$(completed_iters)"; do
    if [[ "$done" -ge "$TARGET_ITERS" ]]; then
      log "100k training complete at iter=$done"
      return 0
    fi
    if ! pgrep -f "finetune_plantuml.py.*uml-plantuml-lora-100k" >/dev/null 2>&1 \
       && ! pgrep -f "run_finetune_resilient.*100k" >/dev/null 2>&1; then
      # Resilient script may be between restarts — check log age
      if tail -1 "$ROOT/data/training/finetune_100k.log" 2>/dev/null | grep -q "Reached $TARGET_ITERS"; then
        log "100k reached per log"
        return 0
      fi
    fi
    sleep 60
  done
}

deploy_100k_if_ok() {
  local best
  best="$(best_val_loss)"
  log "100k best val loss=$best (50k final=$VAL_50K)"
  if python3 - <<PY
best = float("$best")
ref = float("$VAL_50K")
import sys
# Deploy if best val within 15% of 50k final or better
sys.exit(0 if best <= ref * 1.15 else 1)
PY
  then
    log "Val loss acceptable — deploying uml-plantuml-lora-100k"
    if grep -q '^FINETUNED_ADAPTER_PATH=' "$ROOT/.env"; then
      sed -i '' 's|^FINETUNED_ADAPTER_PATH=.*|FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-100k|' "$ROOT/.env"
    else
      echo "FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-100k" >>"$ROOT/.env"
    fi
    bash "$ROOT/scripts/restart_api.sh" || log "API restart failed (non-fatal)"
    "$ROOT/.venv/bin/python" "$ROOT/scripts/smoke_test.py" || log "Smoke test failed (non-fatal)"
  else
    log "WARNING: 100k val loss worse than 50k — keeping FINETUNED_ADAPTER_PATH on 50k adapter"
    log "Investigate finetune_100k.log before deploying 100k weights"
  fi
}

collect_200k_corpus() {
  log "=== Phase 2: download any missing HF corpora ==="
  "$ROOT/.venv/bin/python" "$ROOT/scripts/download_all_corpora.py" --skip-full-stack || true
  log "=== Phase 2: build v2 100k corpus ==="
  env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
    "$ROOT/.venv/bin/python" "$ROOT/scripts/build_corpus_v2_100k.py" --target 100000 --seed 43
  log "=== Phase 2: prepare finetune JSONL for 200k ==="
  env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin" PYTHONPATH="$ROOT" \
    "$ROOT/.venv/bin/python" "$ROOT/scripts/prepare_finetune_data.py" \
    --input data/training/uml_training_combined_200k.parquet \
    --prefer-accepted --valid-ratio 0.02 --test-ratio 0.02
}

train_200k() {
  log "=== Phase 3: warm-start 200k LoRA from 100k adapter ==="
  mkdir -p "$ADAPTER_200K"
  if [[ ! -f "$ADAPTER_200K/adapters.safetensors" ]] && [[ -f "$ADAPTER_100K/adapters.safetensors" ]]; then
    cp "$ADAPTER_100K/adapters.safetensors" "$ADAPTER_200K/"
    log "Copied 100k adapters → 200k adapter dir for warm-start"
  fi
  ADAPTER_PATH="$ADAPTER_200K" ITERS=20000 LOG="$ROOT/data/training/finetune_200k.log" \
    bash "$ROOT/scripts/run_finetune_resilient.sh"
  log "200k training finished"
  if grep -q '^FINETUNED_ADAPTER_PATH=' "$ROOT/.env"; then
    sed -i '' 's|^FINETUNED_ADAPTER_PATH=.*|FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-200k|' "$ROOT/.env"
  fi
  bash "$ROOT/scripts/restart_api.sh" || true
  "$ROOT/.venv/bin/python" "$ROOT/scripts/smoke_test.py" || true
  update_link_file
}

update_link_file() {
  local ui api
  ui=""
  api=""
  [[ -f "$ROOT/data/run/public_ui_url.txt" ]] && ui="$(cat "$ROOT/data/run/public_ui_url.txt")"
  [[ -f "$ROOT/data/run/public_api_url.txt" ]] && api="$(cat "$ROOT/data/run/public_api_url.txt")"
  cat >"$ROOT/Link" <<EOF
UML-Pipeline public demo (Cloudflare quick tunnel)

UI:  ${ui:-https://portable-oxford-supreme-evident.trycloudflare.com}
API: ${api:-https://youth-slide-indicating-marijuana.trycloudflare.com}

Local API: http://127.0.0.1:8000
Adapter:   $(grep FINETUNED_ADAPTER_PATH "$ROOT/.env" | cut -d= -f2)

Updated: $(date -u '+%Y-%m-%d %H:%M UTC')
EOF
  log "Updated Link file"
}

log "==== pipeline_after_100k supervisor started ===="
wait_for_100k
deploy_100k_if_ok
collect_200k_corpus
train_200k
log "==== pipeline_after_100k complete ===="
