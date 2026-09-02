#!/usr/bin/env bash
# Uninstall USER LaunchAgents only (no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UID_NUM="$(id -u)"
AGENT_DIR="${HOME}/Library/LaunchAgents"
LABELS=(
  com.uml.pipeline.api
  com.uml.pipeline.ui
  com.uml.pipeline.tunnels
  com.uml.pipeline.tunnel-monitor
  com.uml.pipeline.git-sync
  com.uml.pipeline.caffeinate
  com.uml.pipeline.ollama24
  com.uml.pipeline.ollama32
)
for label in "${LABELS[@]}"; do
  launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true
  rm -f "${AGENT_DIR}/${label}.plist"
  echo "Removed $label"
done
echo "Done."
