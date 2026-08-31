#!/usr/bin/env bash
# Foreground FastAPI (uvicorn) for launchd KeepAlive.
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
# Prefer portable Java from .env
if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  export PATH="$JAVA_HOME/bin:$PATH"
fi
exec "$ROOT/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000
