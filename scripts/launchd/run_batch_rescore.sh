#!/usr/bin/env bash
# Keep VLM accuracy scoring running for the latest 200-artifact eval batch.
# Managed by com.uml.pipeline.batch-rescore LaunchAgent (KeepAlive).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

IDS_FILE="$ROOT/data/run/batch_new_eval_200_ids.json"
LOG="$ROOT/data/run/batch_rescore_supervisor.log"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') $*" | tee -a "$LOG"; }

if [ ! -f "$IDS_FILE" ]; then
  log "No $IDS_FILE — sleeping 10m"
  sleep 600
  exit 0
fi

# Wait for API (LaunchAgents may start this before API is ready).
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/api/settings/health >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

log "batch-rescore supervisor starting"

pending=$("$ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
from sqlmodel import Session
from app.db import get_engine
from app.models import UMLArtifact
p = Path("data/run/batch_new_eval_200_ids.json")
if not p.is_file():
    print(0); raise SystemExit
ids = json.loads(p.read_text()).get("ids") or []
with Session(get_engine()) as s:
    n = 0
    for i in ids:
        a = s.get(UMLArtifact, i)
        if a and a.render_status == "success" and not (a.composite_score and a.composite_score > 0):
            n += 1
    print(n)
PY
)

if [ "${pending:-0}" -eq 0 ]; then
  log "all batch artifacts scored — sleeping 30m before recheck"
  sleep 1800
  exit 0
fi

log "pending_vlm_scores=$pending"
exec "$ROOT/.venv/bin/python" "$ROOT/scripts/batch_new_eval_200.py" --rescore-only 2>&1 | tee -a "$LOG"
