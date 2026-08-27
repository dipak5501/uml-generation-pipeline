#!/usr/bin/env bash
# Ollama 0.32 on :11435 — watchdog; preserves healthy server / in-flight pulls.
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
OLLAMA_BIN="${OLLAMA32_BIN:-$HOME/Applications/Ollama.app.bak-0.32.1/Contents/Resources/ollama}"
HOST="127.0.0.1:11435"
LOG="${UML_OLLAMA32_LOG:-/tmp/ollama-0.32-qwen.log}"

if [ ! -x "$OLLAMA_BIN" ]; then
  echo "Missing Ollama 0.32 binary: $OLLAMA_BIN" >&2
  exit 1
fi

healthy() {
  curl -sf "http://${HOST}/api/version" >/dev/null 2>&1
}

while healthy; do
  sleep 20
done

port="${HOST##*:}"
pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
if [ -n "$pids" ]; then
  kill $pids 2>/dev/null || true
  sleep 1
fi
exec env OLLAMA_HOST="$HOST" "$OLLAMA_BIN" serve >>"$LOG" 2>&1
