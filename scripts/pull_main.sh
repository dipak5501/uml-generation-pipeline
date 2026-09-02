#!/usr/bin/env bash
# Fast-forward this checkout to origin/main. Does not restart API/UI/tunnels.
# Safe to run while the Mac is screen-locked (LaunchAgents stay up).
# Does NOT source .env (Outlook signatures / stray lines abort bash).
# .env stays untouched because it is gitignored.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  GH_TOKEN="$(bash "$ROOT/scripts/read_env_key.sh" GH_TOKEN "$ROOT/.env" || true)"
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
GH_TOKEN="$(printf '%s' "$GH_TOKEN" | tr -d '\r')"
export GH_TOKEN
export GIT_TERMINAL_PROMPT=0

_git() {
  if [ -n "${GH_TOKEN:-}" ]; then
    git -c credential.helper= \
      -c credential.helper='!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f' \
      "$@"
  else
    git "$@"
  fi
}

BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "Before: ${BRANCH} @ ${BEFORE}"

_git fetch origin main
if [ "$BRANCH" != "main" ]; then
  git checkout -B main origin/main
else
  git reset --hard origin/main
fi

AFTER="$(git rev-parse --short HEAD)"
echo "After:  main @ ${AFTER}"
echo "Working tree is origin/main. .env was not modified."
echo "Next: run restart-api (and restart-ui if UI code changed) so the running process loads this checkout."
