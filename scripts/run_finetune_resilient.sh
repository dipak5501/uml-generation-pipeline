#!/usr/bin/env bash
# Resilient MLX LoRA train: micromamba Open MPI + auto-resume on Metal hiccups.
# IMPORTANT: do NOT put /usr/bin/caffeinate between env and python — SIP strips DYLD_*.
# Idle-aware: lowers BATCH_SIZE when generate jobs are active; backs off further on Metal
# ImpactingInteractivity (common when UI/VLM share the GPU).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=idle_aware_train_lib.sh
source "$ROOT/scripts/idle_aware_train_lib.sh"
OMP_PREFIX="${UML_OPENMPI_PREFIX:-$HOME/micromamba/envs/uml-openmpi}"
ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-50k}"
DATA="${DATA:-data/finetune}"
TARGET_ITERS="${ITERS:-15000}"
BATCH="${BATCH_SIZE:-2}"
IDLE_BATCH="${BATCH_SIZE_IDLE:-$BATCH}"
BUSY_BATCH="${BATCH_SIZE_BUSY:-2}"
LOG="${LOG:-data/training/finetune_50k.log}"
MAX_RESTARTS="${MAX_RESTARTS:-80}"
METAL_SLEEP="${METAL_SLEEP:-45}"
BUSY_WAIT_SECS="${BUSY_WAIT_SECS:-60}"

if [[ ! -d "$OMP_PREFIX/lib" ]]; then
  echo "Missing Open MPI at $OMP_PREFIX — run: micromamba create -y -n uml-openmpi -c conda-forge openmpi" >&2
  exit 1
fi

mkdir -p "$ADAPTER" "$(dirname "$LOG")" "$DATA"

# Keep machine awake without wrapping the python process (SIP-safe).
if ! pgrep -f 'caffeinate -dimsu -w 1' >/dev/null 2>&1; then
  caffeinate -dimsu &
  CAFFEINE_PID=$!
  echo "Started caffeinate pid=$CAFFEINE_PID" | tee -a "$LOG"
fi

pick_batch() {
  if uml_app_is_idle; then
    echo "${IDLE_BATCH}"
  else
    echo "${BUSY_BATCH}"
  fi
}

run_once() {
  local iters="$1"
  local batch="$2"
  local -a args
  args=(
    scripts/finetune_plantuml.py
    --iters "$iters"
    --batch-size "$batch"
    --learning-rate "${LR:-1e-5}"
    --num-layers 8
    --max-seq-length "${MAX_SEQ:-1536}"
    --save-every "${SAVE_EVERY:-200}"
    --steps-per-eval "${STEPS_EVAL:-200}"
    --steps-per-report 20
    --skip-prepare
    --adapter-path "$ADAPTER"
    --data "$DATA"
  )
  if [[ -f "$ADAPTER/adapters.safetensors" ]] || compgen -G "$ADAPTER/*_adapters.safetensors" >/dev/null; then
    args+=(--resume)
  fi
  # Direct env -i → venv python (no SIP intermediary that strips DYLD_*).
  # Do NOT wrap with /usr/bin/nice or caffeinate — SIP strips DYLD_LIBRARY_PATH.
  # Coexistence uses batch throttle + busy-wait instead.
  env -i \
    HOME="$HOME" \
    USER="${USER:-}" \
    TMPDIR="${TMPDIR:-/tmp}" \
    PATH="$ROOT/.venv/bin:$OMP_PREFIX/bin:$HOME/.local/bin:/usr/bin:/bin" \
    DYLD_LIBRARY_PATH="$OMP_PREFIX/lib" \
    DYLD_FALLBACK_LIBRARY_PATH="$OMP_PREFIX/lib" \
    PYTHONPATH="$ROOT" \
    PYTHONUNBUFFERED=1 \
    HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}" \
    "$ROOT/.venv/bin/python" "${args[@]}"
}

completed_iters() {
  python3 - <<PY
import json
import re
from pathlib import Path

adapter = Path("$ADAPTER")
log_path = Path("$LOG")
meta_iters = ckpt_iters = log_iters = 0

meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        d = json.loads(meta.read_text())
        meta_iters = int(d.get("iters_completed") or d.get("iters") or 0)
    except Exception:
        meta_iters = 0

meta_mtime = meta.stat().st_mtime if meta.is_file() else 0.0
numbered = []
for p in adapter.glob("*_adapters.safetensors"):
    head = p.name.split("_")[0]
    if head.isdigit():
        numbered.append((p.stat().st_mtime, int(head), p))
if numbered:
    by_num = max(numbered, key=lambda t: t[1])
    by_mtime = max(numbered, key=lambda t: (t[0], t[1]))
    if by_mtime[1] >= meta_iters:
        ckpt_iters = by_mtime[1]
    elif by_num[1] >= meta_iters:
        ckpt_iters = by_num[1]
    elif by_mtime[0] > meta_mtime and meta_iters > 0:
        # Renumbered continuation newer than meta stamp — do not double-count after stamp.
        ckpt_iters = meta_iters + by_mtime[1]
    else:
        ckpt_iters = by_num[1]

if log_path.is_file():
    text = log_path.read_text(errors="replace")
    attempts = text.split("---- attempt ")
    last = attempts[-1] if attempts else text
    prior = 0
    m = re.search(r"Prior iters=(\d+)", last)
    if m:
        prior = int(m.group(1))
    # Count Train iters only (Val Iter 1 would inflate progress on Metal crashes).
    run_iters = [int(x) for x in re.findall(r"Iter (\d+): Train", last)]
    if run_iters:
        # mlx_lm restarts the Iter counter at 1 on every process start.
        log_iters = prior + max(run_iters) if prior else max(run_iters)

print(max(meta_iters, ckpt_iters, log_iters))
PY
}

stamp_meta() {
  local iters="$1"
  local batch="${2:-$BATCH}"
  python3 - <<PY
import json
from pathlib import Path
adapter = Path("$ADAPTER")
ckpts = sorted(adapter.glob("*_adapters.safetensors"), key=lambda p: p.stat().st_mtime)
iters = int("$iters")
batch = int("$batch")
if iters <= 0 and not ckpts:
    raise SystemExit
data = {
    "base_model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    "adapter_path": str(adapter.resolve()),
    "iters": iters,
    "iters_completed": iters,
    "batch_size": batch,
    "learning_rate": 1e-5,
    "num_layers": 8,
    "max_seq_length": int("${MAX_SEQ:-1536}"),
    "data": str((Path("$ROOT") / "$DATA").resolve()),
    "task": "specification_to_plantuml",
    "target_iters": int("$TARGET_ITERS"),
    "resumed_from": str(ckpts[-1]) if ckpts else None,
    "stopped_early": iters < int("$TARGET_ITERS"),
}
meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        data = {**json.loads(meta.read_text()), **data}
    except Exception:
        pass
meta.write_text(json.dumps(data, indent=2))
PY
}

FORCE_BATCH=""

echo "==== $(date) resilient LoRA train target=$TARGET_ITERS adapter=$ADAPTER idle_batch=$IDLE_BATCH busy_batch=$BUSY_BATCH ====" | tee -a "$LOG"
for attempt in $(seq 1 "$MAX_RESTARTS"); do
  done_iters="$(completed_iters)"
  if [[ "$done_iters" -ge "$TARGET_ITERS" ]]; then
    echo "Reached $done_iters >= $TARGET_ITERS" | tee -a "$LOG"
    exit 0
  fi

  if ! uml_app_is_idle; then
    active="$(uml_active_generate_jobs | tr -d '[:space:]')"
    echo "App busy (active_jobs=${active:-?}); throttle/wait ${BUSY_WAIT_SECS}s before attempt $attempt" | tee -a "$LOG"
    sleep "$BUSY_WAIT_SECS"
  fi

  batch="$(pick_batch)"
  if [[ -n "$FORCE_BATCH" ]] && [[ "$batch" -gt "$FORCE_BATCH" ]]; then
    batch="$FORCE_BATCH"
  fi
  BATCH="$batch"

  echo "---- attempt $attempt at $(date): completed=$done_iters target=$TARGET_ITERS batch=$batch ----" | tee -a "$LOG"
  log_bytes=0
  [[ -f "$LOG" ]] && log_bytes=$(wc -c <"$LOG" | tr -d ' ')

  set +e
  run_once "$TARGET_ITERS" "$batch" >>"$LOG" 2>&1
  rc=$?
  set -e
  done_iters="$(completed_iters)"
  stamp_meta "$done_iters" "$batch" || true
  echo "attempt $attempt exit=$rc completed_now=$done_iters batch=$batch" | tee -a "$LOG"
  if [[ "$done_iters" -ge "$TARGET_ITERS" ]]; then
    exit 0
  fi

  new_tail=$(tail -c +$((log_bytes + 1)) "$LOG" 2>/dev/null || true)
  if echo "$new_tail" | grep -q 'ImpactingInteractivity\|Command buffer execution failed\|\[METAL\]'; then
    next_force=$(( batch / 2 ))
    [[ "$next_force" -lt 1 ]] && next_force=1
    FORCE_BATCH="$next_force"
    echo "Metal/GPU hiccup; drop batch→$FORCE_BATCH, sleep ${METAL_SLEEP}s then resume…" | tee -a "$LOG"
    sleep "$METAL_SLEEP"
    continue
  fi
  if echo "$new_tail" | grep -q 'does not appear to be Open MPI\|MPICH Version'; then
    echo "MPICH still visible — Open MPI DYLD failed; aborting to avoid spin" | tee -a "$LOG"
    exit 250
  fi
  if [[ "$rc" -eq 0 ]]; then
    FORCE_BATCH=""
  fi
  sleep 8
done
echo "Exhausted restarts with completed=$(completed_iters)" | tee -a "$LOG"
exit 1
