#!/usr/bin/env bash
# Restart the LaunchAgent API so code changes (Aya provider, schemas) load.
# Does not require sudo. Safe alongside training — only recycles the API process.
set -euo pipefail
LABEL="com.uml.pipeline.api"
DOMAIN="gui/$(id -u)"
echo "Restarting ${DOMAIN}/${LABEL} …"
if launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null; then
  echo "kickstart ok"
else
  # Fallback: TERM the listener; KeepAlive relaunches run_api.sh
  PID="$(lsof -t -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  if [[ -n "${PID}" ]]; then
    echo "kickstart unavailable — sending TERM to pid ${PID}"
    kill -TERM "${PID}" || true
  else
    echo "No listener on :8000 — bootstrapping agent"
    launchctl bootstrap "${DOMAIN}" "${HOME}/Library/LaunchAgents/${LABEL}.plist" 2>/dev/null \
      || launchctl load -w "${HOME}/Library/LaunchAgents/${LABEL}.plist" 2>/dev/null \
      || true
    launchctl kickstart "${DOMAIN}/${LABEL}" 2>/dev/null || true
  fi
fi
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:8000/api/settings/health || echo 000)"
  if [[ "${code}" == "200" ]]; then
    echo "API healthy (try ${i})"
    curl -s http://127.0.0.1:8000/api/settings/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('status', d.get('status'));
[print(' -', m) for m in d.get('messages',[]) if 'Aya' in m or 'VLM' in m]"
    exit 0
  fi
  sleep 1
done
echo "API did not become healthy in time" >&2
exit 1
