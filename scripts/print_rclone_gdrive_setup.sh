#!/usr/bin/env bash
# Print exact one-time rclone OAuth steps (no passwords). Does not run config.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID_FILE="$ROOT/.gdrive_folder_id"
[[ -f "$ROOT/data/run/google_drive_backup/folder_id.txt" ]] && ID_FILE="$ROOT/data/run/google_drive_backup/folder_id.txt"
FOLDER_ID="$(tr -d '[:space:]' <"$ID_FILE" 2>/dev/null || true)"
FOLDER_ID="${FOLDER_ID:-1gOB2v7HWGD2WJ9zBcPBNY6udai9EeVvh}"
RCLONE="${HOME}/.local/bin/rclone"
[[ -x "$RCLONE" ]] || RCLONE="rclone"
cat <<STEPS
Google Drive backup is waiting for a one-time browser login (rclone OAuth).
A share link / folder id is NOT a Google password and cannot upload by itself.

Destination folder (Editor access required for the account you sign in):
  ${FOLDER_ID}
  https://drive.google.com/drive/folders/${FOLDER_ID}

Run these exact commands in Terminal on this Mac Studio login (033783670).
Do not paste account passwords into chat or into the git repo.

  export PATH="\$HOME/.local/bin:\$PATH"
  ${RCLONE} version
  ${RCLONE} config

In rclone config:
  n          (New remote)
  name       gdrive
  storage    drive     (Google Drive)
  client_id  (leave blank unless you already have one)
  scope      1         (full access)  OR  2 (drive.file) if you prefer narrower
  service_account_file  (leave blank)
  Edit advanced?  n
  Use web browser to authenticate?  y
  Complete the Google browser window as the account that has Editor on the folder.
  Keep this remote?  y
  q          (Quit config)

Then verify the shared folder (not your whole Drive root):

  ${RCLONE} lsd gdrive: --drive-root-folder-id ${FOLDER_ID}

Then start incremental backup (LaunchAgent will also pick this up):

  bash ${ROOT}/scripts/backup_to_google_drive.sh

Uploads are incremental (rclone copy, few transfers, time-sliced). LoRA is not
stopped. Live uml_app.db is copied, never deleted. Secrets are excluded.
STEPS
