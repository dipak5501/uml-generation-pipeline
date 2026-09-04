#!/usr/bin/env bash
# Idle-aware self-training loop: harvest accepted artifacts → mix corpora → LoRA resume.
# Yields GPU to industrial finetune (com.uml.pipeline.finetune-industrial) and live API.
# Does NOT change FINETUNED_ADAPTER_PATH / live API adapter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-adaptation}"
DATA="${DATA:-data/finetune_adaptation}"
LOG="${LOG:-data/training/self_train.log}"
STATE="${STATE:-data/run/self_train_state.json}"
WARM="${WARM_START:-models/uml-plantuml-lora-sourcecode-30k}"
INDUSTRIAL_ADAPTER="${INDUSTRIAL_ADAPTER:-models/uml-plantuml-lora-industrial-complete}"
CYCLE_ITERS="${CYCLE_ITERS:-400}"
MIN_HARVEST="${MIN_HARVEST:-32}"
SLEEP_BUSY="${SLEEP_BUSY:-900}"
MAX_LOAD="${MAX_LOAD:-10.0}"

mkdir -p "$ADAPTER" "$DATA" "$(dirname "$LOG")" "$(dirname "$STATE")" data/training data/run

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $*" | tee -a "$LOG"; }

write_state() {
  local status="$1"
  local detail="${2:-}"
  "$ROOT/.venv/bin/python" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
prev = {}
if p.is_file():
    try:
        prev = json.loads(p.read_text())
    except Exception:
        prev = {}
prev.update({
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "status": """$status""",
    "detail": """$detail""",
    "adapter": "$ADAPTER",
    "data": "$DATA",
    "live_adapter_unchanged": "models/uml-plantuml-lora-sourcecode-30k",
    "switch_when_ready": (
        "After industrial adapter reaches target iters and eval looks good, set "
        "FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-industrial-complete "
        "(or models/uml-plantuml-lora-adaptation for continual top-up) and restart API."
    ),
})
p.write_text(json.dumps(prev, indent=2))
PY
}

gpu_busy() {
  # Yield while industrial trainer (script or mlx python on that adapter) is active.
  if pgrep -f 'run_finetune_industrial\.sh' >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -f 'uml-plantuml-lora-industrial' >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -f 'finetune_industrial_complete' >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

api_busy() {
  "$ROOT/.venv/bin/python" - <<'PY' 2>/dev/null || echo 0
from sqlmodel import Session, select
from app.db import get_engine
from app.models import GenerationJob
n = 0
try:
    with Session(get_engine()) as s:
        for j in s.exec(select(GenerationJob).where(GenerationJob.status == "running")).all():
            n += 1
except Exception:
    n = 0
print(n)
PY
}

load_too_high() {
  "$ROOT/.venv/bin/python" - <<PY
import os
load = os.getloadavg()[0]
print("1" if load >= float("$MAX_LOAD") else "0")
PY
}

# --- always harvest + rebuild mix (cheap; no GPU) ---
log "self-train: harvesting accepted artifacts"
"$ROOT/.venv/bin/python" "$ROOT/scripts/harvest_accepted_for_finetune.py" >>"$LOG" 2>&1 || true
harvest_n="$("$ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
p = Path("data/training/accepted_harvest_manifest.json")
if not p.is_file():
    print(0)
else:
    print(int(json.loads(p.read_text()).get("row_count") or 0))
PY
)"
log "self-train: harvest_rows=$harvest_n"

log "self-train: building adaptation mix + JSONL (rich: full industrial + source30k + scenarios + harvest)"
"$ROOT/.venv/bin/python" "$ROOT/scripts/build_adaptation_finetune_mix.py" \
  --industrial-sample "${ADAPT_INDUSTRIAL_SAMPLE:-8901}" \
  --source-sample "${ADAPT_SOURCE_SAMPLE:-6000}" \
  --scenario-sample "${ADAPT_SCENARIO_SAMPLE:-1000}" \
  >>"$LOG" 2>&1 || {
  log "mix/prepare failed; will retry later"
  write_state "harvest_only" "mix failed"
  sleep "$SLEEP_BUSY"
  exit 0
}

if [[ "${harvest_n:-0}" -lt "$MIN_HARVEST" ]]; then
  log "self-train: harvest <$MIN_HARVEST — skip LoRA cycle"
  write_state "waiting_for_samples" "harvest=$harvest_n"
  sleep "$SLEEP_BUSY"
  exit 0
fi

if gpu_busy; then
  log "self-train: GPU busy (industrial / peer trainer) — yield ${SLEEP_BUSY}s"
  write_state "yielded_gpu" "industrial or peer finetune active"
  sleep "$SLEEP_BUSY"
  exit 0
fi

running_jobs="$(api_busy | tr -d '[:space:]')"
if [[ "${running_jobs:-0}" -gt 0 ]]; then
  log "self-train: API has $running_jobs running generation job(s) — yield"
  write_state "yielded_api" "running_jobs=$running_jobs"
  sleep 300
  exit 0
fi

if [[ "$(load_too_high)" == "1" ]]; then
  log "self-train: load average high — yield"
  write_state "yielded_load" "load>=$MAX_LOAD"
  sleep 600
  exit 0
fi

# Warm-start adaptation adapter once (prefer completed industrial if present & past live).
if [[ ! -f "$ADAPTER/adapters.safetensors" ]] && [[ ! -f "$ADAPTER/0000100_adapters.safetensors" ]]; then
  if [[ -f "$INDUSTRIAL_ADAPTER/adapters.safetensors" ]] \
    && [[ -f "$INDUSTRIAL_ADAPTER/finetune_meta.json" ]] \
    && "$ROOT/.venv/bin/python" - <<PY
import json
from pathlib import Path
m = json.loads(Path("$INDUSTRIAL_ADAPTER/finetune_meta.json").read_text())
done = int(m.get("iters_completed") or 0)
target = int(m.get("target_iters") or m.get("iters") or 0)
# Only warm from industrial once it has at least reached a full prior target (e.g. 4000+)
# and is not mid-tiny-warmup; prefer industrial when complete (>= target) else sourcecode-30k.
raise SystemExit(0 if done >= max(target, 4000) else 1)
PY
  then
    cp "$INDUSTRIAL_ADAPTER/adapters.safetensors" "$ADAPTER/adapters.safetensors"
    [[ -f "$INDUSTRIAL_ADAPTER/adapter_config.json" ]] && cp "$INDUSTRIAL_ADAPTER/adapter_config.json" "$ADAPTER/adapter_config.json"
    log "Warm-start from industrial → $ADAPTER"
  elif [[ -f "$WARM/adapters.safetensors" ]]; then
    cp "$WARM/adapters.safetensors" "$ADAPTER/adapters.safetensors"
    [[ -f "$WARM/adapter_config.json" ]] && cp "$WARM/adapter_config.json" "$ADAPTER/adapter_config.json"
    log "Warm-start from $WARM → $ADAPTER"
  fi
fi

# Incremental target: resume from completed + CYCLE_ITERS
done_now="$("$ROOT/.venv/bin/python" - <<PY
import json, re
from pathlib import Path
adapter = Path("$ADAPTER")
meta_iters = ckpt_iters = 0
meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        d = json.loads(meta.read_text())
        meta_iters = int(d.get("iters_completed") or d.get("iters") or 0)
    except Exception:
        pass
ckpts = sorted(adapter.glob("*_adapters.safetensors"), key=lambda p: int(p.name.split("_")[0]) if p.name.split("_")[0].isdigit() else 0)
if ckpts:
    ckpt_iters = int(ckpts[-1].name.split("_")[0])
print(max(meta_iters, ckpt_iters))
PY
)"
target=$(( done_now + CYCLE_ITERS ))
log "self-train: LoRA cycle done=$done_now → target=$target adapter=$ADAPTER"
write_state "training" "target=$target harvest=$harvest_n"

export ADAPTER_PATH="$ADAPTER"
export DATA
export ITERS="$target"
export BATCH_SIZE="${BATCH_SIZE:-4}"
export MAX_SEQ="${MAX_SEQ:-1536}"
export SAVE_EVERY="${SAVE_EVERY:-100}"
export STEPS_EVAL="${STEPS_EVAL:-100}"
export LOG
export MAX_RESTARTS="${MAX_RESTARTS:-8}"

set +e
bash "$ROOT/scripts/run_finetune_resilient.sh"
rc=$?
set -e

log "self-train: cycle exit=$rc"
write_state "cycle_done" "exit=$rc target=$target"
# Interval agent: exit 0 so StartInterval can fire again; KeepAlive agent uses SuccessfulExit=false.
sleep 60
exit 0
