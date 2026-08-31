#!/usr/bin/env bash
# Run MLX LoRA finetune with micromamba Open MPI (avoids Anaconda MPICH).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OMP_PREFIX="${UML_OPENMPI_PREFIX:-$HOME/micromamba/envs/uml-openmpi}"
if [[ ! -d "$OMP_PREFIX/lib" ]]; then
  echo "Missing Open MPI env at $OMP_PREFIX" >&2
  echo "Create with: micromamba create -y -n uml-openmpi -c conda-forge openmpi" >&2
  exit 1
fi
ADAPTER="${ADAPTER_PATH:-models/uml-plantuml-lora-50k}"
ITERS="${ITERS:-15000}"
exec env -i \
  HOME="$HOME" \
  USER="${USER:-}" \
  TMPDIR="${TMPDIR:-/tmp}" \
  PATH="$ROOT/.venv/bin:$OMP_PREFIX/bin:$HOME/.local/bin:/usr/bin:/bin" \
  DYLD_LIBRARY_PATH="$OMP_PREFIX/lib" \
  DYLD_FALLBACK_LIBRARY_PATH="$OMP_PREFIX/lib" \
  PYTHONPATH="$ROOT" \
  PYTHONUNBUFFERED=1 \
  HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}" \
  "$ROOT/.venv/bin/python" scripts/finetune_plantuml.py \
  --iters "$ITERS" \
  --batch-size "${BATCH_SIZE:-4}" \
  --learning-rate "${LR:-1e-5}" \
  --num-layers 8 \
  --max-seq-length 2048 \
  --save-every "${SAVE_EVERY:-500}" \
  --steps-per-eval 250 \
  --steps-per-report 50 \
  --skip-prepare \
  --adapter-path "$ADAPTER" \
  "$@"
