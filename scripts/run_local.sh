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

# Dual Ollama for paper VLMs (0.24 mllama + 0.32 qwen)
if [ -x "$ROOT/scripts/ensure_ollama_dual.sh" ]; then
  bash "$ROOT/scripts/ensure_ollama_dual.sh" || true
elif ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
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

# Detach into a new session so IDE/Cursor shells cannot kill servers when
# their terminal ends (plain `nohup … &` still shares the process group).
: >"$API_LOG"
: >"$UI_LOG"
"$PY" - "$PID_DIR/api.pid" "$API_LOG" "$UVICORN" app.main:app --host 127.0.0.1 --port 8000 <<'PY'
import os, subprocess, sys
pid_file, log_path, *cmd = sys.argv[1:]
with open(log_path, "a") as log:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=os.environ.get("PWD") or os.getcwd(),
        env=os.environ.copy(),
    )
open(pid_file, "w").write(str(proc.pid))
print(proc.pid)
PY

"$PY" - "$PID_DIR/ui.pid" "$UI_LOG" "$STREAMLIT" run ui/streamlit_app.py \
  --server.port 8501 --server.address 127.0.0.1 --server.headless true <<'PY'
import os, subprocess, sys
pid_file, log_path, *cmd = sys.argv[1:]
with open(log_path, "a") as log:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=os.environ.get("PWD") or os.getcwd(),
        env=os.environ.copy(),
    )
open(pid_file, "w").write(str(proc.pid))
print(proc.pid)
PY

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
