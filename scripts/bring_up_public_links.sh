#!/usr/bin/env bash
# One-shot Mac Studio bring-up: local API/UI, Cloudflare tunnels, GitHub Link.md.
# Must run ON the Mac (Darwin). This Linux cloud agent cannot start trycloudflare.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "ERROR: run this on the Mac Studio, not a Linux cloud VM." >&2
  echo "  cd /Users/033783670/Desktop/uml-generation-pipeline-main" >&2
  echo "  bash scripts/bring_up_public_links.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "== git (main) =="
git fetch origin main
git checkout main
git pull origin main

echo "== local API / UI =="
if ! curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8000/api/settings/health \
  || ! curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8501/; then
  echo "Local services down — installing user LaunchAgents"
  bash "$ROOT/scripts/install_macos_user_server.sh"
  bash "$ROOT/scripts/install_tunnel_monitor.sh"
fi
bash "$ROOT/scripts/macos_server_status.sh" || true

echo "== Cloudflare tunnels =="
bash "$ROOT/scripts/start_public_tunnels.sh"

echo "== publish GitHub Link.md =="
if ! bash "$ROOT/scripts/git_push_live_urls.sh"; then
  echo "WARNING: tunnels may be up locally but GitHub Link.md was not updated." >&2
  echo "See /tmp/uml-git-live-urls.log  (check GH_TOKEN in .env — do not print it)" >&2
  exit 1
fi

echo
echo "============================================"
echo "Local URL files (open these — GitHub Link.md should match):"
echo "  UI:  $(tr -d '[:space:]' <"$ROOT/data/run/public_ui_url.txt")"
echo "  API: $(tr -d '[:space:]' <"$ROOT/data/run/public_api_url.txt")"
echo "Keep this macOS user logged in. Do not Log Out."
echo "============================================"
