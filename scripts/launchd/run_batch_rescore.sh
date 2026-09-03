#!/usr/bin/env bash
# Keep VLM accuracy scoring running for the latest 200-artifact eval batch.
# Managed by com.uml.pipeline.batch-rescore LaunchAgent (KeepAlive).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

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

if [ "${pending:-0}" -gt 0 ]; then
  log "pending_vlm_scores=$pending (batch-200 list)"
  exec "$ROOT/.venv/bin/python" "$ROOT/scripts/batch_new_eval_200.py" --rescore-only 2>&1 | tee -a "$LOG"
fi

gallery_pending=$("$ROOT/.venv/bin/python" - <<'PY'
from sqlmodel import Session, select
from app.db import get_engine
from app.models import ModelScore, UMLArtifact

def mock_ids(session):
    found = set()
    for row in session.exec(select(ModelScore)).all():
        text = (row.raw_output or row.explanation or "").lower()
        if "mock vlm" in text:
            found.add(row.artifact_id)
    return found

with Session(get_engine()) as s:
    n = 0
    mocks = mock_ids(s)
    arts = s.exec(select(UMLArtifact).where(UMLArtifact.render_status == "success")).all()
    for a in arts:
        if a.id in mocks or not (a.composite_score and a.composite_score > 0):
            n += 1
    print(n)
PY
)

if [ "${gallery_pending:-0}" -eq 0 ]; then
  log "all successful gallery renders scored — sleeping 30m before recheck"
  sleep 1800
  exit 0
fi

TOKEN="$(bash "$ROOT/scripts/read_env_key.sh" API_ACCESS_TOKEN "$ROOT/.env" || true)"
if [ -z "$TOKEN" ]; then
  log "API_ACCESS_TOKEN missing — cannot POST /rescore; sleeping 5m"
  sleep 300
  exit 1
fi
export API_ACCESS_TOKEN="$TOKEN"

log "gallery_unscored=$gallery_pending — API rescore --unscored-only"
exec "$ROOT/.venv/bin/python" "$ROOT/scripts/rescore_via_api.py" --unscored-only 2>&1 | tee -a "$LOG"
