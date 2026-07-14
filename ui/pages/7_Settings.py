import streamlit as st

from ui.theme import apply_theme

from ui.api_client import API_BASE, api_get

st.set_page_config(page_title="Settings", layout="wide")
apply_theme()
st.title("Settings")

st.write(f"API base URL: `{API_BASE}`")

try:
    health = api_get("/api/settings/health")
    summary = api_get("/api/analytics/summary")
except Exception as exc:
    st.error(f"Health check failed: {exc}")
    st.stop()

st.json(health)

c1, c2, c3 = st.columns(3)
c1.metric("Artifacts", summary.get("total_artifacts", 0))
c2.metric("Render failures", summary.get("render_failures", 0))
c3.metric("Mean score", f"{(summary.get('mean_composite') or 0):.2f}")

if health.get("java_available"):
    st.success("Local Java JDK available — PlantUML renders via jar.")
else:
    st.info(
        "No local Java JDK — that's OK. Diagrams render via the PlantUML HTTP server "
        "(`PLANTUML_REMOTE=true`). Optional: install a JDK for offline rendering."
    )

if summary.get("render_failures", 0) == 0 and summary.get("total_artifacts", 0) > 0:
    st.success("All stored artifacts currently have successful renders.")

if health.get("mock_providers"):
    st.info("Mock providers are ON — ideal for thesis demos without API keys.")
else:
    st.warning("Live providers enabled — ensure models/API keys are configured.")

st.markdown(
    """
### Configuration flags (environment)

| Variable | Purpose |
|----------|---------|
| `MOCK_PROVIDERS` | `true` for offline demo (default) |
| `PLANTUML_REMOTE` | Use plantuml.com when Java is missing (default true) |
| `USE_OLLAMA` | Use local Ollama instead of OpenAI |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Remote OpenAI-compatible API |
| `DATABASE_URL` | SQLite (default) or Postgres URL |

Copy `.env.example` → `.env` and restart the API after changes.
"""
)
