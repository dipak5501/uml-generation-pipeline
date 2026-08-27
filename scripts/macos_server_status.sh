#!/usr/bin/env bash
# Show UML-Pipeline always-on service status (no secrets, no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="$(cat "$ROOT/data/run/launchd_mode.txt" 2>/dev/null || echo unknown)"
LABELS=(
  com.uml.pipeline.api
  com.uml.pipeline.ui
  com.uml.pipeline.tunnels
  com.uml.pipeline.tunnel-monitor
  com.uml.pipeline.caffeinate
  com.uml.pipeline.ollama24
  com.uml.pipeline.ollama32
)

echo "Mode: $MODE (user LaunchAgents — no admin)"
echo "--- launchctl list ---"
for label in "${LABELS[@]}"; do
  launchctl list 2>/dev/null | grep "$label" || echo "$label: not listed"
done

echo "--- local HTTP ---"
curl -sf -o /dev/null -w "api:%{http_code}\n" http://127.0.0.1:8000/api/settings/health || echo "api:down"
curl -sf -o /dev/null -w "ui:%{http_code}\n" http://127.0.0.1:8501/ || echo "ui:down"
echo "--- ollama ---"
curl -sf http://127.0.0.1:11434/api/version 2>/dev/null || echo "11434:down"
echo
curl -sf http://127.0.0.1:11435/api/version 2>/dev/null || echo "11435:down"
echo
echo "--- public URLs ---"
[ -f "$ROOT/data/run/public_ui_url.txt" ] && echo "UI:  $(cat "$ROOT/data/run/public_ui_url.txt")" || echo "UI:  (none yet)"
[ -f "$ROOT/data/run/public_api_url.txt" ] && echo "API: $(cat "$ROOT/data/run/public_api_url.txt")" || echo "API: (none yet)"
echo "--- processes ---"
pgrep -lf 'uvicorn app.main|streamlit run|cloudflared tunnel|caffeinate|ollama serve' 2>/dev/null | head -20 || true
echo "--- reminder ---"
echo "Keep this user logged in. Others: Fast User Switch. Do NOT Log Out."
