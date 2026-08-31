#!/usr/bin/env bash
# Ollama 0.24 on :11434 — watchdog that does not kill a healthy existing server
# (protects in-flight model pulls). If the server dies, starts serve in foreground.
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
OLLAMA_BIN="${OLLAMA24_BIN:-$HOME/Applications/Ollama.app/Contents/Resources/ollama}"
HOST="127.0.0.1:11434"
LOG="${UML_OLLAMA24_LOG:-/tmp/ollama-0.24.log}"

if [ ! -x "$OLLAMA_BIN" ]; then
  echo "Missing Ollama 0.24 binary: $OLLAMA_BIN" >&2
  exit 1
fi

healthy() {
  curl -sf "http://${HOST}/api/version" >/dev/null 2>&1
}

# If already healthy (possibly started outside launchd), wait until it dies.
while healthy; do
  sleep 20
done

# Free port then serve in foreground for KeepAlive
port="${HOST##*:}"
pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
if [ -n "$pids" ]; then
  kill $pids 2>/dev/null || true
  sleep 1
fi
exec env OLLAMA_HOST="$HOST" "$OLLAMA_BIN" serve >>"$LOG" 2>&1
