#!/usr/bin/env bash
# LaunchAgent wrapper for idle-aware self-training / continual LoRA adaptation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec bash "$ROOT/scripts/run_self_training_loop.sh"
