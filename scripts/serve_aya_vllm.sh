#!/usr/bin/env bash
# Serve paper Aya-Vision-8B with vLLM on :8001 (FastAPI already uses :8000).
# Requires NVIDIA CUDA. Do not load Aya in-process on CPU or Apple MPS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  echo "No NVIDIA GPU. Refusing to load Aya-Vision-8B on CPU/MPS." >&2
  echo "Use a CUDA machine, or leave USE_AYA=false." >&2
  exit 1
fi

PORT="${AYA_VLLM_PORT:-8001}"
MODEL="${AYA_VLM_MODEL:-CohereLabs/aya-vision-8b}"
MAX_LEN="${AYA_MAX_MODEL_LEN:-8192}"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "HF_TOKEN is empty. Accept the model license and set HF_TOKEN (never commit it)." >&2
  exit 1
fi

export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"

if command -v vllm >/dev/null 2>&1; then
  exec vllm serve "$MODEL" \
    --port "$PORT" \
    --trust-remote-code \
    --max-model-len "$MAX_LEN" \
    --dtype auto
fi

exec python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --port "$PORT" \
  --trust-remote-code \
  --max-model-len "$MAX_LEN" \
  --dtype auto
