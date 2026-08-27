#!/usr/bin/env bash
# One-shot tunnel ensure — delegates to monitor_public_tunnels.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/scripts/monitor_public_tunnels.sh" --once "$@"
