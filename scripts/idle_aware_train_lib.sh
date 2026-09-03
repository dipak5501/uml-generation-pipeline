#!/usr/bin/env bash
# Shared helpers for idle-aware industrial LoRA training.
# Source from launchd / resilient wrappers. Does not print secrets.

# Active generate jobs (pending|running) in local SQLite app DB.
uml_active_generate_jobs() {
  local db="${1:-data/uml_app.db}"
  if [[ ! -f "$db" ]]; then
    echo 0
    return 0
  fi
  sqlite3 "$db" "SELECT COUNT(*) FROM generationjob WHERE status IN ('pending','running');" 2>/dev/null || echo 0
}

# Minutes since last generate job touch (created or updated). Large = idle.
uml_minutes_since_last_job() {
  local db="${1:-data/uml_app.db}"
  if [[ ! -f "$db" ]]; then
    echo 9999
    return 0
  fi
  sqlite3 "$db" "
    SELECT CAST(
      (julianday('now') - julianday(COALESCE(MAX(updated_at), MAX(created_at), '1970-01-01'))) * 24 * 60
      AS INTEGER
    )
    FROM generationjob;
  " 2>/dev/null || echo 9999
}

# API reachable and reporting ok (no auth / no tokens printed).
uml_api_ok() {
  curl -sf -m 3 http://127.0.0.1:8000/api/settings/health >/dev/null 2>&1
}

# Exit 0 if machine/app looks free for heavy train.
# IDLE_MINUTES: treat as idle when no pending/running AND last job older than N minutes.
uml_app_is_idle() {
  local idle_min="${IDLE_MINUTES:-5}"
  local active
  active="$(uml_active_generate_jobs "${UML_APP_DB:-data/uml_app.db}" | tr -d '[:space:]')"
  active="${active:-0}"
  if [[ "$active" =~ ^[0-9]+$ ]] && [[ "$active" -gt 0 ]]; then
    return 1
  fi
  local mins
  mins="$(uml_minutes_since_last_job "${UML_APP_DB:-data/uml_app.db}" | tr -d '[:space:]')"
  mins="${mins:-9999}"
  if [[ "$mins" =~ ^[0-9]+$ ]] && [[ "$mins" -lt "$idle_min" ]]; then
    return 1
  fi
  return 0
}

# Choose batch: high when idle, low when busy. Respects BATCH_SIZE_IDLE / BATCH_SIZE_BUSY.
uml_pick_batch_size() {
  local idle_bs="${BATCH_SIZE_IDLE:-${BATCH_SIZE:-8}}"
  local busy_bs="${BATCH_SIZE_BUSY:-2}"
  if uml_app_is_idle; then
    echo "$idle_bs"
  else
    echo "$busy_bs"
  fi
}
