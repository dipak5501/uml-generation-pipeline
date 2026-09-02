#!/usr/bin/env bash
# Start Cloudflare quick tunnels for Streamlit UI (:8501) and FastAPI (:8000).
# No Cloudflare account required. URLs change each run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared missing. Install to ~/.local/bin/cloudflared" >&2
  exit 1
fi

mkdir -p "$ROOT/data/run" /tmp
UI_LOG="${UML_TUNNEL_UI_LOG:-/tmp/uml-tunnel-ui.log}"
API_LOG="${UML_TUNNEL_API_LOG:-/tmp/uml-tunnel-api.log}"
UI_URL_FILE="$ROOT/data/run/public_ui_url.txt"
API_URL_FILE="$ROOT/data/run/public_api_url.txt"

: >"$UI_LOG"
: >"$API_LOG"
rm -f "$UI_URL_FILE" "$API_URL_FILE"

# Kill prior quick tunnels we started
pkill -f "cloudflared tunnel --url http://127.0.0.1:8501" 2>/dev/null || true
pkill -f "cloudflared tunnel --url http://127.0.0.1:8000" 2>/dev/null || true
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8501" 2>/dev/null || true
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000" 2>/dev/null || true
sleep 1

extract_url() {
  local log="$1" out="$2"
  for _ in $(seq 1 90); do
    # try.cloudflare.com HTTPS URL (exclude api.trycloudflare.com from error text)
    url="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$log" 2>/dev/null \
      | grep -vE 'https://api\.trycloudflare\.com' | head -1 || true)"
    if [ -n "$url" ]; then
      printf '%s\n' "$url" >"$out"
      echo "$url"
      return 0
    fi
    if grep -q "429 Too Many Requests\|error code: 1015" "$log" 2>/dev/null; then
      return 1
    fi
    sleep 0.5
  done
  return 1
}

start_one_tunnel() {
  local port="$1" log="$2" pidfile="$3" label="$4"
  local attempt pid url
  for attempt in 1 2 3 4 5; do
    : >"$log"
    # nohup: the parent script exits; without this, bash SIGHUPs cloudflared
    # (Cloudflare 1033 — tunnel name exists, connector gone).
    nohup cloudflared tunnel --protocol http2 --url "http://127.0.0.1:${port}" >"$log" 2>&1 &
    pid=$!
    disown "$pid" 2>/dev/null || true
    echo "$pid" >"$pidfile"
    # Write URL to file once; do not double-echo into command substitution.
    if extract_url "$log" "${log}.url" >/dev/null; then
      url="$(tr -d '[:space:]' <"${log}.url")"
      printf '%s\n' "$url"
      return 0
    fi
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    if grep -q "429 Too Many Requests\|error code: 1015" "$log" 2>/dev/null; then
      echo "Cloudflare rate limit on $label tunnel (attempt $attempt/5); waiting..." >&2
      sleep $((attempt * 60))
    else
      echo "$label tunnel failed (attempt $attempt/5)" >&2
      tail -5 "$log" >&2 || true
      sleep 5
    fi
  done
  return 1
}

echo "Waiting for tunnel URLs..."
UI_URL="$(start_one_tunnel 8501 "$UI_LOG" "$ROOT/data/run/tunnel_ui.pid" UI)" \
  || { echo "UI tunnel failed"; tail -40 "$UI_LOG"; exit 1; }
printf '%s\n' "$UI_URL" >"$UI_URL_FILE"
sleep 3
API_URL="$(start_one_tunnel 8000 "$API_LOG" "$ROOT/data/run/tunnel_api.pid" API)" \
  || { echo "API tunnel failed"; tail -40 "$API_LOG"; exit 1; }
printf '%s\n' "$API_URL" >"$API_URL_FILE"

"$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" publish \
  --ui "$UI_URL" --api "$API_URL" --reason "manual tunnel start" || true

if ! bash "$ROOT/scripts/git_push_live_urls.sh"; then
  echo "WARNING: tunnels are up but GitHub Link.md was NOT updated." >&2
  echo "See /tmp/uml-git-live-urls.log (GH_TOKEN in .env — do not print it)." >&2
fi

echo
echo "============================================"
echo "Browser UI (open this on any device):"
echo "  $UI_URL"
echo "Public API (docs / exports — browser only):"
echo "  $API_URL"
echo "  $API_URL/docs"
echo "Streamlit→API (local, required):"
echo "  http://127.0.0.1:8000"
echo "============================================"
echo "Streamlit sends Authorization: Bearer <API_ACCESS_TOKEN> automatically"
echo "from .env (same token as API). Token is set in .env — do not commit it."
echo "Logs: $UI_LOG  $API_LOG"
echo "Restart later:  bash scripts/start_public_tunnels.sh"
echo "Auto-monitor:   bash scripts/monitor_public_tunnels.sh --loop"
echo "Keep Mac awake:  caffeinate -dimsu &   (or System Settings → Energy)"
