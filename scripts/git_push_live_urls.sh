#!/usr/bin/env bash
# Push Cloudflare tunnel URL docs to origin/main from ANY local branch.
# Does not run pytest (markdown only). Never commits .env, data/, or models/.
#
# Does NOT `source .env` (Outlook signatures / stray lines abort the push).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG_TAG="[git-live-urls]"
LOG_FILE="${UML_LIVE_URL_LOG:-/tmp/uml-git-live-urls.log}"
STATUS_FILE="${UML_LIVE_URL_STATUS:-$ROOT/data/run/github_url_push.status}"
WT="${UML_LIVE_URL_WORKTREE:-$ROOT/.live-url-worktree}"
BRANCH_TMP="_live-url-push"
log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $LOG_TAG $*" | tee -a "$LOG_FILE"; }

write_status() {
  mkdir -p "$(dirname "$STATUS_FILE")"
  printf '%s\n' "$1" >"$STATUS_FILE"
}

# Read GH_TOKEN without executing .env (strips CR). Existing env wins.
if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  GH_TOKEN="$(bash "$ROOT/scripts/read_env_key.sh" GH_TOKEN "$ROOT/.env" || true)"
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
# Never leak a token that was pasted with a trailing \r into git credentials.
GH_TOKEN="$(printf '%s' "$GH_TOKEN" | tr -d '\r')"
export GH_TOKEN

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
  write_status "skipped: no live-URL files"
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
  write_status "ok: origin/main already current"
  exit 0
fi

git commit -m "chore: update public Cloudflare tunnel URLs"

_redact() {
  # Drop token-shaped strings from git/credential errors.
  sed -E 's/github_pat_[A-Za-z0-9_]+/<redacted-pat>/g; s/ghp_[A-Za-z0-9]+/<redacted-pat>/g; s/:[^\/:@]+@/:<redacted>@/g'
}

_push_with_token() {
  local err
  err="$(mktemp)"
  # Ignore stored helpers (stale PAT in macOS Keychain / origin URL).
  if ! GIT_TERMINAL_PROMPT=0 git \
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
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main
  log "Pushed live URLs to origin/main via gh (${FILES[*]})"
  write_status "ok: pushed via gh ${FILES[*]}"
  exit 0
fi

log "No GH_TOKEN or gh auth; live URLs committed locally on $BRANCH_TMP only."
write_status "failed: no GH_TOKEN in .env and gh not logged in"
exit 1
