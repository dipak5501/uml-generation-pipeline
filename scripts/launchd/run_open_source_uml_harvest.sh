#!/usr/bin/env bash
# Periodic open-source UML top-up for the *next* industrial CONTINUOUS pass.
# Does not stop mlx / finetune-industrial; only refreshes DATA files on disk.
# Does not touch live FINETUNED_ADAPTER_PATH or delete uml_app.db / artifacts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG="${HARVEST_LOG:-data/training/open_source_uml_harvest.log}"
mkdir -p "$(dirname "$LOG")"

# Skip if industrial training is mid Metal-heavy start (optional soft gate).
# Staging JSONL while a pass is running is OK: mlx loads data at attempt start.
echo "==== $(date) open-source UML harvest start ====" | tee -a "$LOG"
set +e
env -i HOME="$HOME" PATH="$ROOT/.venv/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin" \
  PYTHONPATH="$ROOT" \
  "$ROOT/.venv/bin/python" scripts/stage_open_source_uml_topup.py >>"$LOG" 2>&1
rc=$?
set -e
echo "==== $(date) open-source UML harvest done rc=$rc ====" | tee -a "$LOG"
exit 0
