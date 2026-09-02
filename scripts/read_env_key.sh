#!/usr/bin/env bash
# Print one KEY from a .env file. Does not source/execute the file.
# Usage: bash scripts/read_env_key.sh KEY [path/to/.env]
set -euo pipefail
KEY="${1:?usage: read_env_key.sh KEY [envfile]}"
FILE="${2:-.env}"
[ -f "$FILE" ] || exit 0
# Last assignment wins. Strip CR (Outlook/Windows), optional quotes, export prefix.
line="$(grep -E "^[[:space:]]*(export[[:space:]]+)?${KEY}=" "$FILE" | tail -1 | tr -d '\r' || true)"
[ -n "$line" ] || exit 0
val="${line#*=}"
val="${val#\"}"
val="${val%\"}"
val="${val#\'}"
val="${val%\'}"
printf '%s' "$val"
