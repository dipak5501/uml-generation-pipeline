#!/usr/bin/env bash
# Install periodic Google Drive backup LaunchAgent for login 033783670 (no sudo).
# Interval default 45 minutes so LoRA is not disk-starved. Incremental ticks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
INTERVAL_SEC="${GDRIVE_BACKUP_INTERVAL_SEC:-2700}"  # default 45 minutes

# Persist shared-folder id locally (gitignored). Not a password.
FOLDER_ID="${UML_GDRIVE_FOLDER_ID:-1gOB2v7HWGD2WJ9zBcPBNY6udai9EeVvh}"
mkdir -p "$ROOT/data/run/google_drive_backup"
printf '%s\n' "$FOLDER_ID" >"$ROOT/data/run/google_drive_backup/folder_id.txt"
printf '%s\n' "$FOLDER_ID" >"$ROOT/.gdrive_folder_id"
printf '%s\n' "https://drive.google.com/drive/folders/${FOLDER_ID}" >"$ROOT/data/run/google_drive_backup/folder_url.txt"
echo "Cursor" >"$ROOT/data/run/google_drive_backup/folder_name.txt"

LABEL="com.uml.pipeline.gdrive-backup"
PROGRAM="$LAUNCHD_DIR/run_google_drive_backup.sh"
STDOUT="$ROOT/data/run/google_drive_backup/launchd.out"
STDERR="$ROOT/data/run/google_drive_backup/launchd.err"
GEN_DIR="$ROOT/data/run/launchd_plists"
DEST="$GEN_DIR/${LABEL}.plist"

chmod +x "$PROGRAM" "$ROOT/scripts/backup_to_google_drive.sh"
mkdir -p "$AGENT_DIR" "$GEN_DIR" "$ROOT/data/run/google_drive_backup"

sed \
  -e "s|LABEL_PLACEHOLDER|$LABEL|g" \
  -e "s|PROGRAM_PLACEHOLDER|$PROGRAM|g" \
  -e "s|ROOT_PLACEHOLDER|$ROOT|g" \
  -e "s|STDOUT_PLACEHOLDER|$STDOUT|g" \
  -e "s|STDERR_PLACEHOLDER|$STDERR|g" \
  -e "s|PATH_PLACEHOLDER|$PATH_VAL|g" \
  -e "s|HOME_PLACEHOLDER|$USER_HOME|g" \
  -e "s|USER_PLACEHOLDER|$(id -un)|g" \
  -e "s|<integer>180</integer>|<integer>${INTERVAL_SEC}</integer>|" \
  "$LAUNCHD_DIR/plist.interval.template.xml" >"$DEST"

launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
cp "$DEST" "$AGENT_DIR/"
launchctl bootstrap "gui/${UID_NUM}" "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || launchctl load -w "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || true
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Installed $LABEL (backup every ${INTERVAL_SEC}s / ~$((INTERVAL_SEC / 60)) min)"
echo "Logs: $STDOUT  $STDERR"
echo "Status: $ROOT/data/run/google_drive_backup/STATUS.txt"
echo "Manual backup: bash $ROOT/scripts/backup_to_google_drive.sh"
echo "Live app keeps local data/; Drive is backup-only (no path rewrite, no LoRA stop)."
echo "This login only: Desktop Documents Downloads Pictures + UML data/models/reports."
echo "If rclone is unauthorized: bash $ROOT/scripts/print_rclone_gdrive_setup.sh"
