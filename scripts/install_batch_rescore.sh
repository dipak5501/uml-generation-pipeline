#!/usr/bin/env bash
# Install KeepAlive LaunchAgent for batch VLM rescoring (accuracy scoring).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LABEL="com.uml.pipeline.batch-rescore"
PROGRAM="$LAUNCHD_DIR/run_batch_rescore.sh"
STDOUT="/tmp/uml-launchd-batch-rescore.out"
STDERR="/tmp/uml-launchd-batch-rescore.err"
GEN_DIR="$ROOT/data/run/launchd_plists"
DEST="$GEN_DIR/${LABEL}.plist"

chmod +x "$PROGRAM"
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
  "$LAUNCHD_DIR/plist.template.xml" >"$DEST"

launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
cp "$DEST" "$AGENT_DIR/"
launchctl bootstrap "gui/${UID_NUM}" "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || launchctl load -w "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || true
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Installed $LABEL (KeepAlive — VLM batch rescoring)"
echo "Logs: $STDOUT  $STDERR  $ROOT/data/run/batch_rescore_supervisor.log"
