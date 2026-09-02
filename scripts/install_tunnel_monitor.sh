#!/usr/bin/env bash
# Install periodic tunnel monitor LaunchAgent (no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
INTERVAL_SEC="${TUNNEL_MONITOR_INTERVAL_SEC:-240}"  # default 4 minutes

LABEL="com.uml.pipeline.tunnel-monitor"
PROGRAM="$LAUNCHD_DIR/run_tunnel_monitor.sh"
STDOUT="/tmp/uml-launchd-tunnel-monitor.out"
STDERR="/tmp/uml-launchd-tunnel-monitor.err"
GEN_DIR="$ROOT/data/run/launchd_plists"
DEST="$GEN_DIR/${LABEL}.plist"

chmod +x "$PROGRAM" "$ROOT/scripts/ensure_public_tunnel.sh" "$ROOT/scripts/tunnel_notify.py" \
  "$ROOT/scripts/git_auto_push.sh" "$ROOT/scripts/git_push_live_urls.sh" \
  "$ROOT/scripts/read_env_key.sh" "$ROOT/scripts/bring_up_public_links.sh" \
  "$ROOT/scripts/auto_sync_all.sh"
mkdir -p "$AGENT_DIR" "$GEN_DIR"

sed \
  -e "s|LABEL_PLACEHOLDER|$LABEL|g" \
  -e "s|PROGRAM_PLACEHOLDER|$PROGRAM|g" \
  -e "s|ROOT_PLACEHOLDER|$ROOT|g" \
  -e "s|STDOUT_PLACEHOLDER|$STDOUT|g" \
  -e "s|STDERR_PLACEHOLDER|$STDERR|g" \
  -e "s|PATH_PLACEHOLDER|$PATH_VAL|g" \
  -e "s|HOME_PLACEHOLDER|$USER_HOME|g" \
  -e "s|USER_PLACEHOLDER|$(id -un)|g" \
  -e "s|<integer>180</integer>|<integer>${INTERVAL_SEC}</integer>|" \
  "$LAUNCHD_DIR/plist.interval.template.xml" >"$DEST"

launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
cp "$DEST" "$AGENT_DIR/"
launchctl bootstrap "gui/${UID_NUM}" "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || launchctl load -w "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || true
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Installed $LABEL (checks every ${INTERVAL_SEC}s)"
echo "Logs: $STDOUT  $STDERR"
echo "Manual check: bash $ROOT/scripts/auto_sync_all.sh"
