#!/usr/bin/env bash
# Auto-commit and push safe changes to GitHub (respects .gitignore).
# Never commits .env, data/, models/, or other ignored paths.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPO="dipak5501/uml-generation-pipeline"
LOG_TAG="[git-auto-push]"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $LOG_TAG $*"; }

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

git config user.name "dipak5501"
git config user.email "dipak5501@users.noreply.github.com"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  log "Not on main (on $BRANCH); skipping."
  exit 0
fi

# Stage safe changes (.gitignore excludes .env, data/, models/, etc.)
git add -u
git add -A

# Belt-and-suspenders: never stage secrets or large local dirs
for forbidden in .env data models output .venv venv; do
  git reset HEAD -- "$forbidden" 2>/dev/null || true
done

if git diff --cached --quiet; then
  log "No safe changes to sync."
  exit 0
fi

# Do not push broken CI — run the same quick gate as GitHub Actions.
if command -v pytest >/dev/null 2>&1; then
  log "Running CI test gate (pytest -q)..."
  if ! MOCK_PROVIDERS=true PYTHONPATH="$ROOT" pytest -q; then
    log "Tests failed; aborting auto-sync (fix locally before next push)."
    git reset HEAD >/dev/null 2>&1 || true
    exit 1
  fi
  log "Tests passed."
else
  log "pytest not found; skipping test gate."
fi

git commit -m "chore: sync local changes"
HASH="$(git rev-parse HEAD)"
log "Committed ${HASH:0:7}"

_push() {
  git -c credential.helper='!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f' \
    push origin main
}

if [ -n "${GH_TOKEN:-}" ]; then
  _push
  log "Pushed to origin/main"
  exit 0
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  git push origin main
  log "Pushed to origin/main (gh auth)"
  exit 0
fi

log "No GH_TOKEN or gh auth; commit local only (${HASH:0:7})."
exit 1
