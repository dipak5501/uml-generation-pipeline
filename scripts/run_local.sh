#!/usr/bin/env bash
# Start UML-Pipeline API + UI and keep them running.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$HOME/Applications/Ollama.app/Contents/Resources:/Applications/Ollama.app/Contents/Resources:$PATH"
export PYTHONPATH="$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

mkdir -p "$ROOT/data" /tmp
API_LOG="${UML_API_LOG:-/tmp/uml-api.log}"
UI_LOG="${UML_UI_LOG:-/tmp/uml-ui.log}"
PID_DIR="${UML_PID_DIR:-$ROOT/data/run}"
mkdir -p "$PID_DIR"

# Ensure Ollama
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve > /tmp/ollama-serve.log 2>&1 &
    sleep 2
  else
    open -a Ollama 2>/dev/null || open "$HOME/Applications/Ollama.app" 2>/dev/null || true
    sleep 3
  fi
fi

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}

stop_port 8000
stop_port 8501

PY="$ROOT/.venv/bin/python"
UVICORN="$ROOT/.venv/bin/uvicorn"
STREAMLIT="$ROOT/.venv/bin/streamlit"

if [ ! -x "$UVICORN" ]; then
  echo "Missing venv. Run: make install" >&2
  exit 1
fi

nohup "$UVICORN" app.main:app --host 127.0.0.1 --port 8000 >"$API_LOG" 2>&1 &
echo $! >"$PID_DIR/api.pid"

nohup "$STREAMLIT" run ui/streamlit_app.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  >"$UI_LOG" 2>&1 &
echo $! >"$PID_DIR/ui.pid"

# Wait until healthy
ok=0
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/settings/health >/dev/null \
     && curl -sf http://127.0.0.1:8501/ >/dev/null; then
    ok=1
    break
  fi
  sleep 0.5
done

echo "API pid=$(cat "$PID_DIR/api.pid")  log=$API_LOG"
echo "UI  pid=$(cat "$PID_DIR/ui.pid")  log=$UI_LOG"
if [ "$ok" -eq 1 ]; then
  echo "READY"
  echo "Open: http://127.0.0.1:8501"
  echo "API:  http://127.0.0.1:8000/docs"
  exit 0
fi

echo "FAILED to become healthy" >&2
tail -40 "$API_LOG" >&2 || true
tail -40 "$UI_LOG" >&2 || true
exit 1
