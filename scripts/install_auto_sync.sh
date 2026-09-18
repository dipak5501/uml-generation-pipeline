#!/usr/bin/env bash
# Install tunnel monitor (3–5 min) + git auto-push + hourly lock-screen watchdog.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

chmod +x "$ROOT/scripts/auto_sync_all.sh" \
  "$ROOT/scripts/git_auto_push.sh" \
  "$ROOT/scripts/monitor_public_tunnels.sh" \
  "$ROOT/scripts/hourly_lock_watchdog.sh" \
  "$ROOT/scripts/launchd/run_git_sync.sh" \
  "$ROOT/scripts/launchd/run_tunnel_monitor.sh" \
  "$ROOT/scripts/launchd/run_hourly_watchdog.sh"

TUNNEL_MONITOR_INTERVAL_SEC="${TUNNEL_MONITOR_INTERVAL_SEC:-240}" \
  bash "$ROOT/scripts/install_tunnel_monitor.sh"

GIT_SYNC_INTERVAL_SEC="${GIT_SYNC_INTERVAL_SEC:-3600}" \
  bash "$ROOT/scripts/install_git_sync.sh"

HOURLY_WATCHDOG_INTERVAL_SEC="${HOURLY_WATCHDOG_INTERVAL_SEC:-3600}" \
  bash "$ROOT/scripts/install_hourly_watchdog.sh"

echo
echo "Full automation installed (lock-screen safe — stay logged in, lock OK):"
echo "  com.uml.pipeline.tunnel-monitor   (every ${TUNNEL_MONITOR_INTERVAL_SEC:-240}s)"
echo "  com.uml.pipeline.git-sync         (every ${GIT_SYNC_INTERVAL_SEC:-3600}s)"
echo "  com.uml.pipeline.hourly-watchdog  (every ${HOURLY_WATCHDOG_INTERVAL_SEC:-3600}s)"
echo "Manual one-shot: bash $ROOT/scripts/hourly_lock_watchdog.sh"
echo "Status file:     $ROOT/data/run/hourly_watchdog_status.md"
