#!/usr/bin/env bash
# Incremental backup of THIS Mac Studio login (033783670) to a shared Google Drive folder.
# Past files upload over repeated LaunchAgent runs; new files keep syncing.
# Never moves/deletes live paths. Safe alongside LoRA (nice + lock + time slice).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGIN_USER="033783670"
LOGIN_HOME="/Users/${LOGIN_USER}"
BACKUP_NAME="${UML_GDRIVE_BACKUP_NAME:-033783670-mac-studio}"
DEFAULT_FOLDER_ID="1gOB2v7HWGD2WJ9zBcPBNY6udai9EeVvh"
LOG_DIR="$ROOT/data/run/google_drive_backup"
STATUS_FILE="$LOG_DIR/STATUS.txt"
LAST_SYNC_FILE="$LOG_DIR/last_sync.txt"
LOCK_DIR="$LOG_DIR/backup.lockdir"
FILTER_FILE="$ROOT/scripts/gdrive_rclone_filters.txt"
CURSOR_FILE="$LOG_DIR/source_cursor.txt"
FOLDER_ID_FILE="$LOG_DIR/folder_id.txt"
FOLDER_NAME_FILE="$LOG_DIR/folder_name.txt"
GITIGNORED_ID_FILE="$ROOT/.gdrive_folder_id"
# Cap each LaunchAgent tick so the machine stays usable; next interval resumes.
MAX_SECS="${UML_GDRIVE_MAX_SECS:-1200}"
BW_LIMIT="${UML_GDRIVE_BWLIMIT:-8M}"

mkdir -p "$LOG_DIR"

persist_folder_id() {
  local id="$1"
  [[ -n "$id" ]] || return 0
  printf '%s\n' "$id" >"$FOLDER_ID_FILE"
  printf '%s\n' "$id" >"$GITIGNORED_ID_FILE"
  printf '%s\n' "https://drive.google.com/drive/folders/${id}" >"$LOG_DIR/folder_url.txt"
}

load_drive_folder_id() {
  local id
  if [[ -n "${UML_GDRIVE_FOLDER_ID:-}" ]]; then
    printf '%s\n' "${UML_GDRIVE_FOLDER_ID}"
    return 0
  fi
  for f in "$FOLDER_ID_FILE" "$GITIGNORED_ID_FILE"; do
    if [[ -f "$f" ]]; then
      id="$(tr -d '[:space:]' <"$f")"
      if [[ -n "$id" ]]; then
        printf '%s\n' "$id"
        return 0
      fi
    fi
  done
  printf '%s\n' "$DEFAULT_FOLDER_ID"
  return 0
}

load_drive_folder_name() {
  local name
  if [[ -n "${UML_GDRIVE_FOLDER_NAME:-}" ]]; then
    printf '%s\n' "${UML_GDRIVE_FOLDER_NAME}"
    return 0
  fi
  if [[ -f "$FOLDER_NAME_FILE" ]]; then
    name="$(head -n 1 "$FOLDER_NAME_FILE" | sed 's/[[:space:]]*$//')"
    if [[ -n "$name" ]]; then
      printf '%s\n' "$name"
      return 0
    fi
  fi
  printf '%s\n' "Cursor"
}

rclone_bin() {
  if [[ -n "${UML_RCLONE_BIN:-}" && -x "${UML_RCLONE_BIN}" ]]; then
    printf '%s\n' "${UML_RCLONE_BIN}"
    return 0
  fi
  if command -v rclone >/dev/null 2>&1; then
    command -v rclone
    return 0
  fi
  if [[ -x "${HOME}/.local/bin/rclone" ]]; then
    printf '%s\n' "${HOME}/.local/bin/rclone"
    return 0
  fi
  return 1
}

log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] $*" | tee -a "$LOG_DIR/backup.log"
}

write_status() {
  cat >"$STATUS_FILE" <<EOF
updated_at=$(date '+%Y-%m-%d %H:%M:%S %Z')
drive_found=$1
drive_root=${2:-}
backup_dest=${3:-}
last_result=$4
notes=$5
login_home=$LOGIN_HOME
backup_name=$BACKUP_NAME
EOF
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" >"$LOCK_DIR/pid"
    return 0
  fi
  local old_pid=""
  if [[ -f "$LOCK_DIR/pid" ]]; then
    old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  fi
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    return 1
  fi
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" 2>/dev/null || return 1
  echo "$$" >"$LOCK_DIR/pid"
  return 0
}

release_lock() {
  rm -rf "$LOCK_DIR" 2>/dev/null || true
}

# This job is only for user 033783670 — never walk /Users/<someone-else>.
assert_this_login() {
  if [[ "$(id -un)" != "$LOGIN_USER" ]]; then
    log "REFUSE: backup is only for login ${LOGIN_USER}, current=$(id -un)"
    write_status "no" "" "" "refused_wrong_user" "not_${LOGIN_USER}"
    exit 1
  fi
  if [[ "${HOME}" != "$LOGIN_HOME" ]]; then
    log "REFUSE: HOME must be ${LOGIN_HOME}, got ${HOME}"
    write_status "no" "" "" "refused_wrong_home" "home_mismatch"
    exit 1
  fi
}

path_is_this_login() {
  local p="$1"
  case "$p" in
    "$LOGIN_HOME"|"$LOGIN_HOME"/*) return 0 ;;
    *) return 1 ;;
  esac
}

find_google_drive_root() {
  local cand base mydrive

  if [[ -n "${UML_GDRIVE_ROOT:-}" && -d "${UML_GDRIVE_ROOT}" && -w "${UML_GDRIVE_ROOT}" ]]; then
    printf '%s\n' "${UML_GDRIVE_ROOT}"
    return 0
  fi

  if [[ -d "${HOME}/Library/CloudStorage" ]]; then
    shopt -s nullglob
    for base in "${HOME}/Library/CloudStorage"/GoogleDrive-*; do
      [[ -d "$base" ]] || continue
      for mydrive in "$base/My Drive" "$base/MyDrive" "$base"; do
        if [[ -d "$mydrive" && -w "$mydrive" ]]; then
          printf '%s\n' "$mydrive"
          shopt -u nullglob
          return 0
        fi
      done
    done
    shopt -u nullglob
  fi

  for cand in \
    "${HOME}/Google Drive/My Drive" \
    "${HOME}/Google Drive" \
    "${HOME}/GoogleDrive/My Drive" \
    "${HOME}/GoogleDrive" \
    "/Volumes/GoogleDrive/My Drive" \
    "/Volumes/GoogleDrive"
  do
    if [[ -d "$cand" && -w "$cand" ]]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

find_rclone_dest() {
  local bin remotes remote
  bin="$(rclone_bin)" || return 1
  remotes="$("$bin" listremotes 2>/dev/null || true)"
  [[ -n "$remotes" ]] || return 1
  while IFS= read -r remote; do
    remote="${remote%:}"
    [[ -n "$remote" ]] || continue
    case "$(printf '%s' "$remote" | tr '[:upper:]' '[:lower:]')" in
      gdrive|google|google-drive|googledrive|googleone|google-one)
        printf '%s\n' "${remote}:"
        return 0
        ;;
    esac
  done <<<"$remotes"
  while IFS= read -r remote; do
    remote="${remote%:}"
    [[ -n "$remote" ]] || continue
    printf '%s\n' "${remote}:"
    return 0
  done <<<"$remotes"
  return 1
}

# label|abs_src|dest_rel
SOURCES=()

add_source() {
  local label="$1" src="$2" dest="$3"
  [[ -e "$src" ]] || return 0
  path_is_this_login "$src" || return 0
  SOURCES+=("${label}|${src}|${dest}")
}

build_sources() {
  SOURCES=()
  # Priority: UML project artifacts (also live under Desktop; copy first so they land soon).
  add_source "uml-data" "$ROOT/data" "uml-pipeline/data"
  add_source "uml-models" "$ROOT/models" "uml-pipeline/models"
  add_source "uml-reports" "$ROOT/reports" "uml-pipeline/reports"
  add_source "uml-output" "$ROOT/output" "uml-pipeline/output"
  add_source "uml-sample" "$ROOT/sample_data" "uml-pipeline/sample_data"
  # Login work folders (this user only).
  add_source "Desktop" "$LOGIN_HOME/Desktop" "Desktop"
  add_source "Documents" "$LOGIN_HOME/Documents" "Documents"
  add_source "Downloads" "$LOGIN_HOME/Downloads" "Downloads"
  add_source "Pictures" "$LOGIN_HOME/Pictures" "Pictures"
  add_source "Movies" "$LOGIN_HOME/Movies" "Movies"
  add_source "Music" "$LOGIN_HOME/Music" "Music"
  add_source "Public" "$LOGIN_HOME/Public" "Public"
  add_source "Applications" "$LOGIN_HOME/Applications" "Applications"
  # Extra login data that is not Library (Library holds Keychains / browser logins).
  add_source "ollama" "$LOGIN_HOME/.ollama" "dot-ollama"
  add_source "micromamba" "$LOGIN_HOME/micromamba" "micromamba"
}

RSYNC_EXCLUDES=(
  --exclude '.env'
  --exclude '.env.local'
  --exclude '.env.production'
  --exclude 'API_ACCESS_TOKEN'
  --exclude 'GH_TOKEN'
  --exclude '.git'
  --exclude '.venv'
  --exclude 'venv'
  --exclude 'node_modules'
  --exclude '__pycache__'
  --exclude '.pytest_cache'
  --exclude '.DS_Store'
  --exclude 'credentials.json'
  --exclude 'service_account.json'
  --exclude '*.pem'
  --exclude '*.key'
  --exclude '.ssh'
  --exclude '.Trash'
  --exclude 'Caches'
  --exclude '.cache'
  --exclude 'Keychains'
)

elapsed_ok() {
  local now
  now="$(date +%s)"
  (( now - START_EPOCH < MAX_SECS ))
}

sync_rsync_one() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  log "rsync copy (no delete): $src -> $dest"
  # --update: incremental; no --delete: never remove live or Drive extras.
  if ! "${NICE[@]}" rsync -a --update --partial \
    "${RSYNC_EXCLUDES[@]}" \
    "$src/" "$dest/"; then
    return 1
  fi
  find "$dest" \( -name '.env' -o -name 'API_ACCESS_TOKEN' -o -name 'GH_TOKEN' \) -type f -delete 2>/dev/null || true
  return 0
}

sync_rclone_one() {
  local src="$1" dest_path="$2"
  local remaining now rc
  now="$(date +%s)"
  remaining=$((MAX_SECS - (now - START_EPOCH)))
  if (( remaining < 30 )); then
    return 47
  fi
  log "rclone copy (incremental, ${remaining}s budget): $src -> ${BACKUP_NAME}/${dest_path}"
  set +e
  "${NICE[@]}" "$RCLONE_BIN" copy "$src" "${RCLONE_REMOTE}${BACKUP_NAME}/${dest_path}" \
    "${RCLONE_ROOT_FLAGS[@]}" \
    --filter-from "$FILTER_FILE" \
    --create-empty-src-dirs \
    --transfers 2 --checkers 4 --tpslimit 4 \
    --bwlimit "$BW_LIMIT" \
    --drive-chunk-size 64M \
    --fast-list \
    --max-duration "${remaining}s" \
    --cutoff-mode soft \
    --retries 2 \
    --low-level-retries 5
  rc=$?
  set -e
  return "$rc"
}

write_oauth_next_step() {
  local folder_id="$1"
  cat >"$LOG_DIR/NEXT_STEP.txt" <<EOF
Google Drive backup cannot start uploads yet (rclone is not authorized).

Configured destination folder id (gitignored locally):
  ${folder_id}
  https://drive.google.com/drive/folders/${folder_id}

A share link is NOT a Google login. Authorize rclone once in a browser.

Exact commands on this Mac (user ${LOGIN_USER}):

  export PATH="\$HOME/.local/bin:\$PATH"
  rclone version
  rclone config

  n                    # New remote
  gdrive               # name
  drive                # Google Drive storage
  (blank client id)
  1                    # scope: full Drive access  (or 2 = drive.file)
  (blank service account)
  n                    # no advanced
  y                    # Use web browser to authenticate
  # complete the Google window as the account with Editor on the folder
  y                    # keep remote
  q                    # quit

  rclone lsd gdrive: --drive-root-folder-id ${folder_id}
  bash ${ROOT}/scripts/backup_to_google_drive.sh

Or: bash ${ROOT}/scripts/print_rclone_gdrive_setup.sh

Uploads are incremental (not one giant copy). LoRA is not stopped.
Live DB/files stay on disk. Secrets (.env, .ssh, Keychains) are excluded.
Other macOS users under /Users are not backed up.
EOF
}

assert_this_login

DRIVE_FOLDER_ID="$(load_drive_folder_id)"
DRIVE_FOLDER_NAME="$(load_drive_folder_name)"
persist_folder_id "$DRIVE_FOLDER_ID"

build_sources
if [[ ${#SOURCES[@]} -eq 0 ]]; then
  log "ERROR: no source paths under $LOGIN_HOME"
  write_status "no" "" "" "error" "no_source_dirs"
  exit 1
fi

if ! acquire_lock; then
  log "SKIP: another backup is already running"
  write_status "unknown" "" "" "skipped_locked" "another_backup_running"
  exit 0
fi
trap release_lock EXIT

START_EPOCH="$(date +%s)"
NICE=(nice -n 19)
START_INDEX=0
if [[ -f "$CURSOR_FILE" ]]; then
  START_INDEX="$(tr -d '[:space:]' <"$CURSOR_FILE" || echo 0)"
  [[ "$START_INDEX" =~ ^[0-9]+$ ]] || START_INDEX=0
  if (( START_INDEX >= ${#SOURCES[@]} )); then
    START_INDEX=0
  fi
fi

log "Login backup for ${LOGIN_USER} -> folder id ${DRIVE_FOLDER_ID}"
log "Sources (${#SOURCES[@]}): starting at index ${START_INDEX}; max ${MAX_SECS}s this tick"
log "Excludes: .env .ssh Keychains Caches .Trash .venv node_modules tokens (see ${FILTER_FILE})"

if RCLONE_REMOTE="$(find_rclone_dest)"; then
  RCLONE_BIN="$(rclone_bin)"
  RCLONE_ROOT_FLAGS=()
  if [[ -n "$DRIVE_FOLDER_ID" ]]; then
    RCLONE_ROOT_FLAGS=(--drive-root-folder-id "$DRIVE_FOLDER_ID")
    log "rclone ${RCLONE_REMOTE} --drive-root-folder-id ${DRIVE_FOLDER_ID}"
  else
    log "rclone remote ${RCLONE_REMOTE} (folder id missing)"
  fi
  SYNC_OK=1
  TIMED_OUT=0
  i=0
  n=${#SOURCES[@]}
  for ((k=0; k<n; k++)); do
    i=$(( (START_INDEX + k) % n ))
    IFS='|' read -r label src dest_rel <<<"${SOURCES[$i]}"
    if ! elapsed_ok; then
      printf '%s\n' "$i" >"$CURSOR_FILE"
      TIMED_OUT=1
      log "TIME SLICE: resume next interval at [$i] $label"
      break
    fi
    rc=0
    sync_rclone_one "$src" "$dest_rel" || rc=$?
    if [[ $rc -eq 47 ]]; then
      printf '%s\n' "$i" >"$CURSOR_FILE"
      TIMED_OUT=1
      log "TIME SLICE (rclone max-duration): resume at [$i] $label"
      break
    elif [[ $rc -ne 0 ]]; then
      log "WARN: rclone copy failed for $label (rc=$rc)"
      SYNC_OK=0
    else
      log "rclone copy done: $label"
    fi
  done
  if [[ $TIMED_OUT -eq 0 ]]; then
    printf '%s\n' 0 >"$CURSOR_FILE"
  fi
  result="ok"
  [[ $SYNC_OK -eq 1 ]] || result="partial"
  [[ $TIMED_OUT -eq 0 ]] || result="in_progress"
  write_status "rclone" "$RCLONE_REMOTE" "${RCLONE_REMOTE}${BACKUP_NAME}" \
    "$result" "incremental_copy;no_delete;drive_root_folder_id=${DRIVE_FOLDER_ID};lora_untouched"
  {
    echo "synced_at=$(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "mode=rclone_copy_incremental"
    echo "folder_id=$DRIVE_FOLDER_ID"
    echo "sources_count=${#SOURCES[@]}"
    echo "cursor=$(cat "$CURSOR_FILE" 2>/dev/null || echo 0)"
  } >"$LAST_SYNC_FILE"
  log "rclone tick finished ($result)"
  exit 0
fi

DRIVE_ROOT=""
if DRIVE_ROOT="$(find_google_drive_root)"; then
  DEST="${DRIVE_ROOT}/${BACKUP_NAME}"
  if [[ -n "$DRIVE_FOLDER_NAME" && -d "${DRIVE_ROOT}/${DRIVE_FOLDER_NAME}" ]]; then
    DEST="${DRIVE_ROOT}/${DRIVE_FOLDER_NAME}/${BACKUP_NAME}"
  fi
  mkdir -p "$DEST"
  log "Google Drive mount at: $DRIVE_ROOT"
  log "rsync destination: $DEST (rclone not authorized; mount is best-effort)"
  SYNC_OK=1
  TIMED_OUT=0
  n=${#SOURCES[@]}
  for ((k=0; k<n; k++)); do
    i=$(( (START_INDEX + k) % n ))
    IFS='|' read -r label src dest_rel <<<"${SOURCES[$i]}"
    local_dest="${DEST}/${dest_rel}"
    if ! elapsed_ok; then
      printf '%s\n' "$i" >"$CURSOR_FILE"
      TIMED_OUT=1
      log "TIME SLICE: resume next interval at $label"
      break
    fi
    if ! sync_rsync_one "$src" "$local_dest"; then
      log "WARN: rsync failed for $label"
      SYNC_OK=0
    fi
  done
  if [[ $TIMED_OUT -eq 0 ]]; then
    printf '%s\n' 0 >"$CURSOR_FILE"
  fi
  result="ok"
  [[ $SYNC_OK -eq 1 ]] || result="partial"
  [[ $TIMED_OUT -eq 0 ]] || result="in_progress"
  write_status "yes" "$DRIVE_ROOT" "$DEST" "$result" "rsync_update_no_delete;prefer_rclone_for_shared_folder_id"
  log "rsync tick finished ($result)"
  exit 0
fi

log "Google Drive is not mounted and rclone is not authorized."
log "Folder id ${DRIVE_FOLDER_ID} is saved (gitignored). One browser OAuth is required."
write_oauth_next_step "$DRIVE_FOLDER_ID"
write_status "no" "" "" "waiting_for_rclone" \
  "rclone_config_once;grant_Editor_on_shared_folder;incremental_after_oauth"
bash "$ROOT/scripts/print_rclone_gdrive_setup.sh" | tee -a "$LOG_DIR/backup.log"
exit 0
