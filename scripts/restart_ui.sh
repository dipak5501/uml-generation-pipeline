#!/usr/bin/env bash
# Restart the LaunchAgent Streamlit UI so .env / api_client changes load.
set -euo pipefail
LABEL="com.uml.pipeline.ui"
DOMAIN="gui/$(id -u)"
echo "Restarting ${DOMAIN}/${LABEL} …"
if launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null; then
  echo "kickstart ok"
else
  PID="$(lsof -t -nP -iTCP:8501 -sTCP:LISTEN 2>/dev/null | head -1 || true)"
  if [[ -n "${PID}" ]]; then
    echo "kickstart unavailable — sending TERM to pid ${PID}"
    kill -TERM "${PID}" || true
  else
    echo "No listener on :8501 — bootstrapping agent"
    launchctl bootstrap "${DOMAIN}" "${HOME}/Library/LaunchAgents/${LABEL}.plist" 2>/dev/null \
      || launchctl load -w "${HOME}/Library/LaunchAgents/${LABEL}.plist" 2>/dev/null \
      || true
    launchctl kickstart "${DOMAIN}/${LABEL}" 2>/dev/null || true
  fi
fi
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:8501/ || echo 000)"
  if [[ "${code}" == "200" ]]; then
    echo "UI healthy (try ${i})"
    exit 0
  fi
  sleep 1
done
echo "UI did not become healthy in time" >&2
exit 1
