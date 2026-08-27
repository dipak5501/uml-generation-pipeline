#!/usr/bin/env bash
# Dual Cloudflare quick tunnels (HTTP/2) for launchd KeepAlive.
# When either tunnel exits, this process exits so launchd restarts both and refreshes URLs.
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
cd "$ROOT"
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
CLOUDFLARED="${CLOUDFLARED:-$HOME/.local/bin/cloudflared}"
if [ ! -x "$CLOUDFLARED" ]; then
  echo "cloudflared missing at $CLOUDFLARED" >&2
  exit 1
fi

mkdir -p "$ROOT/data/run" /tmp
UI_LOG="${UML_TUNNEL_UI_LOG:-/tmp/uml-tunnel-ui.log}"
API_LOG="${UML_TUNNEL_API_LOG:-/tmp/uml-tunnel-api.log}"
UI_URL_FILE="$ROOT/data/run/public_ui_url.txt"
API_URL_FILE="$ROOT/data/run/public_api_url.txt"
: >"$UI_LOG"
: >"$API_LOG"

# Free prior tunnel processes (do not touch unrelated cloudflared)
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8501" 2>/dev/null || true
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000" 2>/dev/null || true
sleep 1

"$CLOUDFLARED" tunnel --protocol http2 --url http://127.0.0.1:8501 >"$UI_LOG" 2>&1 &
UI_PID=$!
echo "$UI_PID" >"$ROOT/data/run/tunnel_ui.pid"
"$CLOUDFLARED" tunnel --protocol http2 --url http://127.0.0.1:8000 >"$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" >"$ROOT/data/run/tunnel_api.pid"

extract_url() {
  local log="$1" out="$2"
  for _ in $(seq 1 90); do
    url="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$log" 2>/dev/null \
      | grep -vE 'https://api\.trycloudflare\.com' | head -1 || true)"
    if [ -n "$url" ]; then
      printf '%s\n' "$url" >"$out"
      echo "$url"
      return 0
    fi
    sleep 0.5
  done
  return 1
}

UI_URL="$(extract_url "$UI_LOG" "$UI_URL_FILE")" || { kill "$UI_PID" "$API_PID" 2>/dev/null || true; exit 1; }
API_URL="$(extract_url "$API_LOG" "$API_URL_FILE")" || { kill "$UI_PID" "$API_PID" 2>/dev/null || true; exit 1; }

"$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" publish \
  --ui "$UI_URL" --api "$API_URL" \
  --reason "LaunchAgent tunnel supervisor restarted tunnels" 2>/dev/null || true

bash "$ROOT/scripts/git_auto_push.sh" >/dev/null 2>&1 || true

# Soft-restart UI so it reloads .env (localhost API_BASE_URL)
UID_NUM="$(id -u)"
launchctl kickstart -k "gui/${UID_NUM}/com.uml.pipeline.ui" 2>/dev/null \
  || launchctl kill SIGTERM "gui/${UID_NUM}/com.uml.pipeline.ui" 2>/dev/null \
  || true

echo "UI_URL=$UI_URL"
echo "API_URL=$API_URL"
echo "API_BASE_URL=http://127.0.0.1:8000"

cleanup() {
  kill "$UI_PID" "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Block until a tunnel dies or public URLs fail → launchd KeepAlive restarts
while kill -0 "$UI_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 30
  if ! "$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" check --quiet; then
    echo "Public URL health check failed — restarting tunnels" >&2
    exit 1
  fi
done
exit 1
