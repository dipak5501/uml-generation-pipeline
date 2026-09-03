#!/usr/bin/env bash
# Periodic Google Drive backup for this Mac Studio login (033783670).
set -euo pipefail
ROOT="/Users/033783670/Desktop/uml-generation-pipeline-main"
export HOME="/Users/033783670"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"
exec bash "$ROOT/scripts/backup_to_google_drive.sh"
