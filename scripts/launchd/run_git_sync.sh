#!/usr/bin/env bash
# Periodic git auto-sync for launchd StartInterval (every 45 minutes).
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
exec bash "$ROOT/scripts/git_auto_push.sh"
