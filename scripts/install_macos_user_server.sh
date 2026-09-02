#!/usr/bin/env bash
# Install UML-Pipeline as USER LaunchAgents only (NO sudo / NO admin).
#
# Survives: Cursor quit, Terminal close, screen lock.
# Does NOT survive: full Log Out of this macOS user.
# Workable multi-user path: keep this account logged in; others use
# Fast User Switching (not Log Out). Lock screen is fine.
#
# True logout-proof LaunchDaemons require admin — not available here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_NAME="$(id -un)"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$USER_HOME/Applications/Ollama.app/Contents/Resources"

chmod +x "$LAUNCHD_DIR"/run_*.sh
mkdir -p "$AGENT_DIR" "$ROOT/data/run"

SERVICES=(
  "com.uml.pipeline.api|$LAUNCHD_DIR/run_api.sh|/tmp/uml-launchd-api.out|/tmp/uml-launchd-api.err"
  "com.uml.pipeline.ui|$LAUNCHD_DIR/run_ui.sh|/tmp/uml-launchd-ui.out|/tmp/uml-launchd-ui.err"
  "com.uml.pipeline.tunnels|$LAUNCHD_DIR/run_tunnels.sh|/tmp/uml-launchd-tunnels.out|/tmp/uml-launchd-tunnels.err"
  "com.uml.pipeline.caffeinate|$LAUNCHD_DIR/run_caffeinate.sh|/tmp/uml-launchd-caffeinate.out|/tmp/uml-launchd-caffeinate.err"
  "com.uml.pipeline.ollama24|$LAUNCHD_DIR/run_ollama24.sh|/tmp/uml-launchd-ollama24.out|/tmp/uml-launchd-ollama24.err"
  "com.uml.pipeline.ollama32|$LAUNCHD_DIR/run_ollama32.sh|/tmp/uml-launchd-ollama32.out|/tmp/uml-launchd-ollama32.err"
)

render_plist() {
  local label="$1" program="$2" stdout="$3" stderr="$4" dest="$5"
  sed \
    -e "s|LABEL_PLACEHOLDER|$label|g" \
    -e "s|PROGRAM_PLACEHOLDER|$program|g" \
    -e "s|ROOT_PLACEHOLDER|$ROOT|g" \
    -e "s|STDOUT_PLACEHOLDER|$stdout|g" \
    -e "s|STDERR_PLACEHOLDER|$stderr|g" \
    -e "s|PATH_PLACEHOLDER|$PATH_VAL|g" \
    -e "s|HOME_PLACEHOLDER|$USER_HOME|g" \
    -e "s|USER_PLACEHOLDER|$USER_NAME|g" \
    "$LAUNCHD_DIR/plist.template.xml" >"$dest"
}

echo "Installing USER LaunchAgents (no sudo) for $USER_NAME ..."
echo "Stopping prior API/UI/tunnel listeners (keeping Ollama pulls/serve)..."
for port in 8000 8501; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then kill $pids 2>/dev/null || true; fi
done
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8501" 2>/dev/null || true
pkill -f "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000" 2>/dev/null || true
pkill -x caffeinate 2>/dev/null || true
sleep 2

GEN_DIR="$ROOT/data/run/launchd_plists"
mkdir -p "$GEN_DIR"

for entry in "${SERVICES[@]}"; do
  IFS='|' read -r label program stdout stderr <<<"$entry"
  plist_path="$GEN_DIR/${label}.plist"
  render_plist "$label" "$program" "$stdout" "$stderr" "$plist_path"
  launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true
  rm -f "${AGENT_DIR}/${label}.plist"
  cp "$plist_path" "$AGENT_DIR/"
  launchctl bootstrap "gui/${UID_NUM}" "$AGENT_DIR/${label}.plist" 2>/dev/null \
    || launchctl load -w "$AGENT_DIR/${label}.plist" 2>/dev/null \
    || true
  launchctl enable "gui/${UID_NUM}/${label}" 2>/dev/null || true
  launchctl kickstart -k "gui/${UID_NUM}/${label}" 2>/dev/null || true
  echo "  loaded $label"
done

printf 'agent\n' >"$ROOT/data/run/launchd_mode.txt"
printf 'gui/%s\n' "$UID_NUM" >"$ROOT/data/run/launchd_domain.txt"

echo "Waiting for API/UI..."
ok=0
for _ in $(seq 1 45); do
  if curl -sf http://127.0.0.1:8000/api/settings/health >/dev/null \
     && curl -sf http://127.0.0.1:8000/api/agent/health >/dev/null \
     && curl -sf http://127.0.0.1:8501/ >/dev/null; then
    ok=1
    break
  fi
  sleep 1
done

# Give tunnels a moment to write URLs
sleep 5

echo
echo "======== UML-Pipeline USER server ========"
echo "Mode: LaunchAgents (NO admin)"
if [ "$ok" -eq 1 ]; then
  echo "Local API: http://127.0.0.1:8000/docs"
  echo "Local UI:  http://127.0.0.1:8501"
else
  echo "WARN: API/UI not healthy — see /tmp/uml-launchd-*.err"
fi
[ -f "$ROOT/data/run/public_ui_url.txt" ] && echo "Public UI:  $(cat "$ROOT/data/run/public_ui_url.txt")"
[ -f "$ROOT/data/run/public_api_url.txt" ] && echo "Public API: $(cat "$ROOT/data/run/public_api_url.txt")"
echo
echo "WHAT WORKS WITHOUT ADMIN"
echo "  - Cursor can quit; services keep running"
echo "  - Lock screen / sleep prevented by caffeinate agent"
echo "  - Other people: Fast User Switch (do NOT Log Out this account)"
echo
echo "WHAT DOES NOT WORK WITHOUT ADMIN"
echo "  - Full Log Out of this user stops LaunchAgents"
echo "  - LaunchDaemons / pmset sleep=0 need admin (skipped)"
echo
echo "Status:    bash $ROOT/scripts/macos_server_status.sh"
echo "Uninstall: bash $ROOT/scripts/uninstall_macos_user_server.sh"
echo "=========================================="

# Tunnel watchdog + GitHub Link.md publisher (was a separate install; required
# for always-on public URLs). Safe to re-run.
bash "$ROOT/scripts/install_auto_sync.sh"
