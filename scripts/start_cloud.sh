#!/usr/bin/env bash
# Start API + Streamlit on one host (Render free Web Service).
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}"
export MOCK_PROVIDERS="${MOCK_PROVIDERS:-true}"
export PLANTUML_REMOTE="${PLANTUML_REMOTE:-true}"
export USE_FINETUNED_CODE="${USE_FINETUNED_CODE:-false}"
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/uml_app.db}"

mkdir -p data/artifacts output tools

PORT="${PORT:-8501}"

echo "Starting UML-Pipeline API on :8000 ..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:8000/api/settings/health" >/dev/null; then
    echo "API ready."
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API process died during startup" >&2
    exit 1
  fi
  sleep 1
done

echo "Starting UML-Pipeline UI on :${PORT} ..."
exec streamlit run ui/streamlit_app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false
