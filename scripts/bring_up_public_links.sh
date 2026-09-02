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

echo "== git (follow GitHub main) =="
git fetch origin main
git checkout main
# This Mac is a replica of origin/main. Local unpublished commits (often
# failed auto-sync) must not block tunnels. .env / data/ / models/ are gitignored.
echo "Resetting local main to origin/main (gitignored .env is kept)."
git reset --hard origin/main
git status -sb

echo "== always-on LaunchAgents (API, UI, Ollama, tunnels, URL publish) =="
bash "$ROOT/scripts/install_macos_user_server.sh"
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
