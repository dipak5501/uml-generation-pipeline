#!/usr/bin/env bash
# Push Cloudflare tunnel URL docs to origin/main from ANY local branch.
# Does not run pytest (markdown only). Never commits .env, data/, or models/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG_TAG="[git-live-urls]"
LOG_FILE="${UML_LIVE_URL_LOG:-/tmp/uml-git-live-urls.log}"
WT="${UML_LIVE_URL_WORKTREE:-$ROOT/.live-url-worktree}"
BRANCH_TMP="_live-url-push"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $LOG_TAG $*" | tee -a "$LOG_FILE"; }

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

git config user.name "dipak5501"
git config user.email "dipak5501@users.noreply.github.com"

# Canonical live-URL files. Copy whole files only when they are the Link
# pointers, or when they contain the marked live-demo block (so we do not
# overwrite a newer GitHub README with an older Mac checkout).
CANDIDATES=(
  Link
  Link.md
  README.md
  reports/REVIEWER_PROGRESS_REPORT.md
  reports/REMOTE_CURSOR_ACCESS.md
  docs/deploy.md
)

should_publish() {
  local rel="$1" src="$ROOT/$rel"
  [ -f "$src" ] || return 1
  local base
  base="$(basename "$rel")"
  if [ "$base" = "Link" ] || [ "$base" = "Link.md" ]; then
    grep -q 'trycloudflare.com' "$src" || return 1
    return 0
  fi
  grep -q 'LIVE_DEMO_BEGIN' "$src" && grep -q 'trycloudflare.com' "$src"
}

FILES=()
for rel in "${CANDIDATES[@]}"; do
  if should_publish "$rel"; then
    FILES+=("$rel")
  fi
done

if [ "${#FILES[@]}" -eq 0 ]; then
  log "No live-URL files to publish."
  exit 0
fi

git fetch origin main

cleanup() {
  git worktree remove --force "$WT" 2>/dev/null || true
  rm -rf "$WT"
  git branch -D "$BRANCH_TMP" 2>/dev/null || true
}
trap cleanup EXIT

cleanup
git worktree add -B "$BRANCH_TMP" "$WT" origin/main

for rel in "${FILES[@]}"; do
  mkdir -p "$WT/$(dirname "$rel")"
  cp "$ROOT/$rel" "$WT/$rel"
done

cd "$WT"
git add -- "${FILES[@]}"
if git diff --cached --quiet; then
  log "origin/main already has the current public URLs."
  exit 0
fi

git commit -m "chore: update public Cloudflare tunnel URLs"

_push() {
  git -c credential.helper='!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f' \
    push origin "HEAD:main"
}

if [ -n "${GH_TOKEN:-}" ]; then
  _push
  log "Pushed live URLs to origin/main (${FILES[*]})"
  exit 0
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  git push origin HEAD:main
  log "Pushed live URLs to origin/main via gh (${FILES[*]})"
  exit 0
fi

log "No GH_TOKEN or gh auth; live URLs committed locally on $BRANCH_TMP only."
exit 1
