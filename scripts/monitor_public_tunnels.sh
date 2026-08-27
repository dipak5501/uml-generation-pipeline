#!/usr/bin/env bash
# Health-check Cloudflare quick tunnels; recreate on failure and email new URLs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

INTERVAL="${TUNNEL_MONITOR_INTERVAL:-60}"
LOOP=0
ONCE=0
QUIET=0

usage() {
  cat <<EOF
Usage: bash scripts/monitor_public_tunnels.sh [--loop] [--once] [--interval SEC]

  --loop       Run forever (default when no flag)
  --once       Single health check; recreate + email if unhealthy
  --interval   Seconds between checks (default: 60)
  --quiet      Less console output

Recreates tunnels via scripts/start_public_tunnels.sh when:
  - cloudflared processes are missing, or
  - public UI/API URLs fail HTTP health checks

Requires SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL in .env for email alerts.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --loop) LOOP=1; shift ;;
    --once) ONCE=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [ "$ONCE" -eq 0 ] && [ "$LOOP" -eq 0 ]; then
  LOOP=1
fi

log() {
  [ "$QUIET" -eq 1 ] && return 0
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

read_url_file() {
  local f="$1"
  [ -f "$f" ] && cat "$f" | tr -d '[:space:]' || true
}

tunnel_procs_ok() {
  pgrep -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8501" >/dev/null 2>&1 \
    && pgrep -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000" >/dev/null 2>&1
}

tunnels_agent_loaded() {
  local uid_num
  uid_num="$(id -u)"
  launchctl print "gui/${uid_num}/com.uml.pipeline.tunnels" >/dev/null 2>&1
}

http_ok() {
  local url="$1" path="${2:-/}"
  [ -n "$url" ] || return 1
  # Strip whitespace / accidental multi-line URL file corruption
  url="$(printf '%s' "$url" | tr -d '[:space:]')"
  curl -sf -o /dev/null --max-time 15 "${url%/}${path}"
}

local_services_ok() {
  curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8000/api/settings/health \
    && curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8501/
}

public_ok() {
  "$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" check --quiet
}

sync_link_files() {
  "$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" sync-link >/dev/null 2>&1 || true
}

diagnose() {
  if ! local_services_ok; then
    echo "local API/UI not responding on :8000 / :8501"
    return
  fi
  if ! tunnel_procs_ok; then
    echo "cloudflared tunnel processes not running"
    return
  fi
  local ui api
  ui="$(read_url_file "$ROOT/data/run/public_ui_url.txt")"
  api="$(read_url_file "$ROOT/data/run/public_api_url.txt")"
  if [ -z "$ui" ] || [ -z "$api" ]; then
    echo "public URL files missing or empty"
    return
  fi
  http_ok "$ui" "/" || echo "public UI unreachable: $ui"
  http_ok "$api" "/docs" || echo "public API unreachable: $api"
}

notify_urls() {
  local ui="$1" api="$2" reason="$3"
  if "$ROOT/.venv/bin/python" "$ROOT/scripts/tunnel_notify.py" urls \
      --ui "$ui" --api "$api" --reason "$reason" 2>/dev/null; then
    log "Notification email sent"
  else
    log "WARN: email not sent (check SMTP vars in .env)"
  fi
}

recreate_tunnels() {
  local reason="$1"
  local uid_num ui api
  uid_num="$(id -u)"

  if grep -q "429 Too Many Requests\|error code: 1015" /tmp/uml-tunnel-ui.log /tmp/uml-tunnel-api.log 2>/dev/null; then
    # Only skip when rate-limit lines are fresh (last 30 min of log mtime)
    if find /tmp/uml-tunnel-ui.log /tmp/uml-tunnel-api.log -mmin -30 2>/dev/null | grep -q .; then
      log "Cloudflare rate limit — skipping recreate (retry in ~15 min)"
      return 1
    fi
  fi

  # Prefer LaunchAgent supervisor so we do not fight KeepAlive with a second starter.
  if tunnels_agent_loaded; then
    log "Recreating via LaunchAgent com.uml.pipeline.tunnels ($reason)..."
    launchctl kickstart -k "gui/${uid_num}/com.uml.pipeline.tunnels" 2>/dev/null \
      || launchctl kill SIGTERM "gui/${uid_num}/com.uml.pipeline.tunnels" 2>/dev/null \
      || true
    # Wait for fresh URL files + healthy public endpoints
    for _ in $(seq 1 90); do
      ui="$(read_url_file "$ROOT/data/run/public_ui_url.txt")"
      api="$(read_url_file "$ROOT/data/run/public_api_url.txt")"
      if [ -n "$ui" ] && [ -n "$api" ] && [[ "$ui" != *api.trycloudflare.com* ]] && public_ok; then
        sync_link_files
        log "New UI:  $ui"
        log "New API: $api"
        notify_urls "$ui" "$api" "$reason"
        return 0
      fi
      sleep 2
    done
    log "ERROR: LaunchAgent tunnels did not publish healthy URLs in time"
    return 1
  fi

  log "Recreating public tunnels via start_public_tunnels.sh ($reason)..."
  if ! bash "$ROOT/scripts/start_public_tunnels.sh"; then
    log "ERROR: start_public_tunnels.sh failed"
    return 1
  fi
  ui="$(read_url_file "$ROOT/data/run/public_ui_url.txt")"
  api="$(read_url_file "$ROOT/data/run/public_api_url.txt")"
  sync_link_files
  log "New UI:  $ui"
  log "New API: $api"
  notify_urls "$ui" "$api" "$reason"
}

check_and_fix() {
  if ! local_services_ok; then
    log "WARN: local API/UI down — start services first (make api / make ui or install_macos_user_server.sh)"
    return 1
  fi

  if tunnel_procs_ok && public_ok; then
    sync_link_files
    log "Public tunnels healthy (Link refreshed)"
    return 0
  fi

  local reason="Tunnel health check failed"
  if ! tunnel_procs_ok; then
    reason="cloudflared processes not running"
  elif ! public_ok; then
    reason="public URL HTTP check failed"
  fi
  diagnose | while read -r line; do log "  $line"; done
  recreate_tunnels "$reason"
}

if [ "$ONCE" -eq 1 ]; then
  check_and_fix
  exit $?
fi

log "Tunnel monitor started (interval ${INTERVAL}s). Ctrl+C to stop."
while true; do
  check_and_fix || true
  sleep "$INTERVAL"
done
