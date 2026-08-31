#!/usr/bin/env bash
# Full automation: ensure tunnels → refresh Link/Link.md → commit + push safe files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_TAG="[auto-sync-all]"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $LOG_TAG $*"; }

log "Ensuring public tunnels and refreshing Link..."
bash "$ROOT/scripts/monitor_public_tunnels.sh" --once || true

log "Pushing safe changes to GitHub..."
bash "$ROOT/scripts/git_auto_push.sh"

UI="$(tr -d '[:space:]' <"$ROOT/data/run/public_ui_url.txt" 2>/dev/null || true)"
API="$(tr -d '[:space:]' <"$ROOT/data/run/public_api_url.txt" 2>/dev/null || true)"
HASH="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"

log "Done — UI=$UI API=$API commit=$HASH"
