#!/usr/bin/env bash
# DEPRECATED entrypoint: admin LaunchDaemons are not available on this machine.
# Redirects to user LaunchAgents installer (no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "NOTE: No admin credentials — installing user LaunchAgents only."
echo "      True logout-proof LaunchDaemons are impossible without admin."
exec bash "$ROOT/scripts/install_macos_user_server.sh"
