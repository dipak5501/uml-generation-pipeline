#!/usr/bin/env bash
# Resilient MLX LoRA train: micromamba Open MPI + auto-resume on Metal hiccups.
# IMPORTANT: do NOT put /usr/bin/caffeinate between env and python — SIP strips DYLD_*.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OMP_PREFIX="${UML_OPENMPI_PREFIX:-$HOME/micromamba/envs/uml-openmpi}"
ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-50k}"
TARGET_ITERS="${ITERS:-15000}"
BATCH="${BATCH_SIZE:-2}"
LOG="${LOG:-data/training/finetune_50k.log}"
MAX_RESTARTS="${MAX_RESTARTS:-40}"

if [[ ! -d "$OMP_PREFIX/lib" ]]; then
  echo "Missing Open MPI at $OMP_PREFIX — run: micromamba create -y -n uml-openmpi -c conda-forge openmpi" >&2
  exit 1
fi

mkdir -p "$ADAPTER" "$(dirname "$LOG")"

# Keep machine awake without wrapping the python process (SIP-safe).
if ! pgrep -f 'caffeinate -dimsu -w 1' >/dev/null 2>&1; then
  caffeinate -dimsu &
  CAFFEINE_PID=$!
  echo "Started caffeinate pid=$CAFFEINE_PID" | tee -a "$LOG"
fi

run_once() {
  local iters="$1"
  local -a args
  args=(
    scripts/finetune_plantuml.py
    --iters "$iters"
    --batch-size "$BATCH"
    --learning-rate "${LR:-1e-5}"
    --num-layers 8
    --max-seq-length "${MAX_SEQ:-1536}"
    --save-every "${SAVE_EVERY:-200}"
    --steps-per-eval "${STEPS_EVAL:-200}"
    --steps-per-report 20
    --skip-prepare
    --adapter-path "$ADAPTER"
  )
  if [[ -f "$ADAPTER/adapters.safetensors" ]] || compgen -G "$ADAPTER/*_adapters.safetensors" >/dev/null; then
    args+=(--resume)
  fi
  # Direct env -i → venv python (no SIP intermediary that strips DYLD_*).
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
from pathlib import Path
adapter = Path("$ADAPTER")
meta = adapter / "finetune_meta.json"
if meta.is_file():
    try:
        d = json.loads(meta.read_text())
        print(int(d.get("iters_completed") or d.get("iters") or 0))
        raise SystemExit
    except Exception:
        pass
ckpts = sorted(adapter.glob("*_adapters.safetensors"))
if ckpts:
    print(int(ckpts[-1].name.split("_")[0]))
else:
    print(0)
PY
}

stamp_meta() {
  local iters="$1"
  python3 - <<PY
import json
from pathlib import Path
adapter = Path("$ADAPTER")
ckpts = sorted(adapter.glob("*_adapters.safetensors"))
iters = int("$iters")
if iters <= 0 and not ckpts:
    raise SystemExit
data = {
    "base_model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    "adapter_path": str(adapter.resolve()),
    "iters": iters,
    "iters_completed": iters,
    "batch_size": int("$BATCH"),
    "learning_rate": 1e-5,
    "num_layers": 8,
    "max_seq_length": int("${MAX_SEQ:-1536}"),
    "data": str((Path("$ROOT") / "data" / "finetune").resolve()),
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

echo "==== $(date) resilient LoRA train target=$TARGET_ITERS adapter=$ADAPTER ====" | tee -a "$LOG"
for attempt in $(seq 1 "$MAX_RESTARTS"); do
  done_iters="$(completed_iters)"
  if [[ "$done_iters" -ge "$TARGET_ITERS" ]]; then
    echo "Reached $done_iters >= $TARGET_ITERS" | tee -a "$LOG"
    exit 0
  fi
  echo "---- attempt $attempt at $(date): completed=$done_iters target=$TARGET_ITERS ----" | tee -a "$LOG"
  set +e
  run_once "$TARGET_ITERS" >>"$LOG" 2>&1
  rc=$?
  set -e
  done_iters="$(completed_iters)"
  stamp_meta "$done_iters" || true
  echo "attempt $attempt exit=$rc completed_now=$done_iters" | tee -a "$LOG"
  if [[ "$done_iters" -ge "$TARGET_ITERS" ]]; then
    exit 0
  fi
  if grep -q 'ImpactingInteractivity\|Command buffer execution failed\|\[METAL\]' "$LOG"; then
    echo "Metal/GPU hiccup; sleep 25s then resume…" | tee -a "$LOG"
    sleep 25
    continue
  fi
  if grep -q 'does not appear to be Open MPI\|MPICH Version' <(tail -n 40 "$LOG"); then
    echo "MPICH still visible — Open MPI DYLD failed; aborting to avoid spin" | tee -a "$LOG"
    exit 250
  fi
  sleep 8
done
echo "Exhausted restarts with completed=$(completed_iters)" | tee -a "$LOG"
exit 1
