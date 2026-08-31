#!/usr/bin/env bash
# Uninstall UML-Pipeline launchd services.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UID_NUM="$(id -u)"
MODE="$(cat "$ROOT/data/run/launchd_mode.txt" 2>/dev/null || echo agent)"
LABELS=(
  com.uml.pipeline.api
  com.uml.pipeline.ui
  com.uml.pipeline.tunnels
  com.uml.pipeline.caffeinate
  com.uml.pipeline.ollama24
  com.uml.pipeline.ollama32
)

for label in "${LABELS[@]}"; do
  if [ "$MODE" = "daemon" ] && sudo -n true 2>/dev/null; then
    sudo launchctl bootout "system/${label}" 2>/dev/null || true
    sudo rm -f "/Library/LaunchDaemons/${label}.plist"
  else
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true
    rm -f "${HOME}/Library/LaunchAgents/${label}.plist"
    # Also try daemon cleanup if files leftover
    if [ -f "/Library/LaunchDaemons/${label}.plist" ]; then
      sudo launchctl bootout "system/${label}" 2>/dev/null || true
      sudo rm -f "/Library/LaunchDaemons/${label}.plist" 2>/dev/null || true
    fi
  fi
  echo "Removed $label"
done
echo "Done."
