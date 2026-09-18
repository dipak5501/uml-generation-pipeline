#!/usr/bin/env bash
# LaunchAgent wrapper — hourly lock-screen watchdog.
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
exec bash "$ROOT/scripts/hourly_lock_watchdog.sh"
