#!/usr/bin/env bash
# Ensure dual Ollama servers for paper VLM trio:
#   :11434  Ollama 0.24  — llama3.2-vision (mllama) + llava / Llama text
#   :11435  Ollama 0.32  — qwen2.5vl (newer arch)
set -euo pipefail

OLLAMA24="${HOME}/Applications/Ollama.app/Contents/Resources/ollama"
OLLAMA32="${HOME}/Applications/Ollama.app.bak-0.32.1/Contents/Resources/ollama"
LOG24="${UML_OLLAMA24_LOG:-/tmp/ollama-0.24.log}"
LOG32="${UML_OLLAMA32_LOG:-/tmp/ollama-0.32-qwen.log}"

version_at() {
  local host="$1"
  curl -sf "http://${host}/api/version" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || true
}

ensure_listen() {
  local host="$1"
  curl -sf "http://${host}/api/version" >/dev/null 2>&1
}

start_serve() {
  local bin="$1"
  local host="$2"
  local log="$3"
  if [ ! -x "$bin" ]; then
    echo "Missing ollama binary: $bin" >&2
    return 1
  fi
  # Free the port if something else owns it
  local port="${host##*:}"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
  nohup env OLLAMA_HOST="$host" "$bin" serve >"$log" 2>&1 &
  for _ in $(seq 1 40); do
    ensure_listen "$host" && return 0
    sleep 0.5
  done
  echo "Failed to start Ollama on $host (bin=$bin). See $log" >&2
  return 1
}

# Primary :11434 must be 0.24.x for llama3.2-vision
v24="$(version_at 127.0.0.1:11434)"
if [ -z "$v24" ] || [[ "$v24" != 0.24* ]]; then
  echo "Starting Ollama 0.24 on :11434 (was: ${v24:-down})"
  start_serve "$OLLAMA24" "127.0.0.1:11434" "$LOG24" || true
fi

# Secondary :11435 must be 0.32+ for qwen2.5vl
v32="$(version_at 127.0.0.1:11435)"
if [ -z "$v32" ] || [[ "$v32" == 0.24* ]]; then
  echo "Starting Ollama 0.32 on :11435 (was: ${v32:-down})"
  if [ -x "$OLLAMA32" ]; then
    start_serve "$OLLAMA32" "127.0.0.1:11435" "$LOG32" || true
  else
    echo "WARNING: Ollama 0.32 backup missing ($OLLAMA32); Qwen2.5-VL will fail" >&2
  fi
fi

echo "Ollama :11434 -> $(curl -sf http://127.0.0.1:11434/api/version || echo down)"
echo "Ollama :11435 -> $(curl -sf http://127.0.0.1:11435/api/version || echo down)"
