#!/usr/bin/env bash
# Foreground Streamlit UI for launchd KeepAlive.
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="$ROOT"
mkdir -p "$ROOT/data/run" /tmp
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi
exec "$ROOT/.venv/bin/streamlit" run "$ROOT/ui/streamlit_app.py" \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true
