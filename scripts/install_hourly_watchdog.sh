#!/usr/bin/env bash
# Install hourly lock-screen watchdog LaunchAgent (no sudo).
# Every hour: health-check API/UI/tunnels, refresh Link, push GitHub URLs + safe sync.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
INTERVAL_SEC="${HOURLY_WATCHDOG_INTERVAL_SEC:-3600}"  # default 1 hour

LABEL="com.uml.pipeline.hourly-watchdog"
PROGRAM="$LAUNCHD_DIR/run_hourly_watchdog.sh"
STDOUT="/tmp/uml-launchd-hourly-watchdog.out"
STDERR="/tmp/uml-launchd-hourly-watchdog.err"
GEN_DIR="$ROOT/data/run/launchd_plists"
DEST="$GEN_DIR/${LABEL}.plist"

chmod +x "$PROGRAM" "$ROOT/scripts/hourly_lock_watchdog.sh" \
  "$ROOT/scripts/monitor_public_tunnels.sh" \
  "$ROOT/scripts/git_push_live_urls.sh" \
  "$ROOT/scripts/git_auto_push.sh" \
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

echo "Installed $LABEL (every ${INTERVAL_SEC}s / $((INTERVAL_SEC / 60)) min)"
echo "Logs: $STDOUT  $STDERR"
echo "Status: $ROOT/data/run/hourly_watchdog_status.md"
echo "Manual: bash $ROOT/scripts/hourly_lock_watchdog.sh"
