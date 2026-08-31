#!/usr/bin/env bash
# Periodic tunnel watchdog for launchd StartInterval (every 3 minutes).
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
exec bash "$ROOT/scripts/monitor_public_tunnels.sh" --once --quiet
