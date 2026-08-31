#!/usr/bin/env bash
# Install tunnel monitor (3–5 min) + git auto-push (30–60 min) LaunchAgents.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

chmod +x "$ROOT/scripts/auto_sync_all.sh" \
  "$ROOT/scripts/git_auto_push.sh" \
  "$ROOT/scripts/monitor_public_tunnels.sh" \
  "$ROOT/scripts/launchd/run_git_sync.sh" \
  "$ROOT/scripts/launchd/run_tunnel_monitor.sh"

TUNNEL_MONITOR_INTERVAL_SEC="${TUNNEL_MONITOR_INTERVAL_SEC:-240}" \
  bash "$ROOT/scripts/install_tunnel_monitor.sh"

GIT_SYNC_INTERVAL_SEC="${GIT_SYNC_INTERVAL_SEC:-2700}" \
  bash "$ROOT/scripts/install_git_sync.sh"

echo
echo "Full automation installed:"
echo "  com.uml.pipeline.tunnel-monitor  (every ${TUNNEL_MONITOR_INTERVAL_SEC:-240}s)"
echo "  com.uml.pipeline.git-sync        (every ${GIT_SYNC_INTERVAL_SEC:-2700}s)"
echo "Manual one-shot: bash $ROOT/scripts/auto_sync_all.sh"
