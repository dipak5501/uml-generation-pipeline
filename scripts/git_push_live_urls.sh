#!/usr/bin/env bash
# Push Cloudflare tunnel URL docs to origin/main from ANY local branch.
# Does not run pytest (markdown only). Never commits .env, data/, or models/.
#
# Does NOT `source .env` (Outlook signatures / stray lines abort the push).
# Stays in the repo root (never cd into the worktree) so a concurrent cleanup
# cannot getcwd-fail the push. Unique worktree + mkdir lock avoid two LaunchAgents
# deleting each other's directory.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG_TAG="[git-live-urls]"
LOG_FILE="${UML_LIVE_URL_LOG:-/tmp/uml-git-live-urls.log}"
STATUS_FILE="${UML_LIVE_URL_STATUS:-$ROOT/data/run/github_url_push.status}"
LOCK_DIR="${UML_LIVE_URL_LOCK:-$ROOT/data/run/git_push_live_urls.lockdir}"
WT="${UML_LIVE_URL_WORKTREE:-$ROOT/.live-url-worktree.$$}"
BRANCH_TMP="_live-url-push.$$"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $LOG_TAG $*" | tee -a "$LOG_FILE"; }

write_status() {
  mkdir -p "$(dirname "$STATUS_FILE")"
  printf '%s\n' "$1" >"$STATUS_FILE"
}

mkdir -p "$ROOT/data/run"
# Portable lock (macOS has no flock). mkdir is atomic.
acquired=0
for _ in $(seq 1 180); do
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    acquired=1
    break
  fi
  sleep 1
done
if [ "$acquired" -ne 1 ]; then
  log "Could not acquire live-url push lock."
  write_status "failed: lock timeout"
  exit 1
fi

# Read GH_TOKEN without executing .env (strips CR). Existing env wins.
if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  GH_TOKEN="$(bash "$ROOT/scripts/read_env_key.sh" GH_TOKEN "$ROOT/.env" || true)"
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
GH_TOKEN="$(printf '%s' "$GH_TOKEN" | tr -d '\r')"
export GH_TOKEN

git config user.name "Dipak Yadav"
git config user.email "71300693+dipak5501@users.noreply.github.com"

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
  write_status "skipped: no live-URL files"
  exit 0
fi

git fetch origin main

cleanup() {
  git worktree remove --force "$WT" 2>/dev/null || true
  rm -rf "$WT"
  git branch -D "$BRANCH_TMP" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

cleanup
git worktree add -B "$BRANCH_TMP" "$WT" origin/main

for rel in "${FILES[@]}"; do
  mkdir -p "$WT/$(dirname "$rel")"
  cp "$ROOT/$rel" "$WT/$rel"
done

git -C "$WT" add -- "${FILES[@]}"
if git -C "$WT" diff --cached --quiet; then
  log "origin/main already has the current public URLs."
  write_status "ok: origin/main already current"
  exit 0
fi

git -C "$WT" commit -m "chore: update public Cloudflare tunnel URLs"

_redact() {
  sed -E 's/github_pat_[A-Za-z0-9_]+/<redacted-pat>/g; s/ghp_[A-Za-z0-9]+/<redacted-pat>/g; s/:[^\/:@]+@/:<redacted>@/g'
}

_push_with_token() {
  local err
  err="$(mktemp)"
  if ! GIT_TERMINAL_PROMPT=0 git -C "$WT" \
    -c credential.helper= \
    -c credential.helper='!f() { echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f' \
    push origin "HEAD:main" 2>"$err"; then
    log "git push origin HEAD:main failed:"
    _redact <"$err" | tee -a "$LOG_FILE" >&2
    if grep -Eqi '401|403|invalid|bad credentials|Authentication failed' "$err"; then
      log "GitHub rejected GH_TOKEN. Put a new PAT (Contents: Read and write) in .env on the Mac only — do not paste it in chat."
      write_status "failed: GitHub auth (401/403). Rotate GH_TOKEN in Mac .env"
    else
      write_status "failed: git push (see /tmp/uml-git-live-urls.log)"
    fi
    rm -f "$err"
    return 1
  fi
  rm -f "$err"
  return 0
}

if [ -n "${GH_TOKEN:-}" ]; then
  _push_with_token
  log "Pushed live URLs to origin/main (${FILES[*]})"
  write_status "ok: pushed ${FILES[*]}"
  exit 0
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  GIT_TERMINAL_PROMPT=0 git -C "$WT" push origin HEAD:main
  log "Pushed live URLs to origin/main via gh (${FILES[*]})"
  write_status "ok: pushed via gh ${FILES[*]}"
  exit 0
fi

log "No GH_TOKEN or gh auth; live URLs committed locally on $BRANCH_TMP only."
write_status "failed: no GH_TOKEN in .env and gh not logged in"
exit 1
