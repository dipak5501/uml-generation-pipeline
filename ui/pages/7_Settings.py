import streamlit as st

from ui.api_client import API_BASE, api_get

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")

st.write(f"API base URL: `{API_BASE}`")

try:
    health = api_get("/api/settings/health")
except Exception as exc:
    st.error(f"Health check failed: {exc}")
    st.stop()

st.json(health)

st.markdown(
    """
### Configuration flags (environment)

| Variable | Purpose |
|----------|---------|
| `MOCK_PROVIDERS` | `true` for offline demo (default) |
| `USE_OLLAMA` | Use local Ollama instead of OpenAI |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Remote OpenAI-compatible API |
| `SPEC_MODEL` / `CODE_MODEL` / `VLM_MODELS` | Model names |
| `DATABASE_URL` | SQLite (default) or Postgres URL |
| `MAX_REPAIR_ATTEMPTS` | Repair loop limit |

Copy `.env.example` → `.env` and restart the API after changes.
"""
)

if health.get("java_available"):
    st.success("Java available for PlantUML rendering")
else:
    st.error("Install a JDK so PlantUML can render diagrams")

if health.get("mock_providers"):
    st.info("Mock providers are ON — ideal for thesis demos without API keys.")
else:
    st.warning("Live providers enabled — ensure models/API keys are configured.")
