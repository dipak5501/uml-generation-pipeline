import streamlit as st

from ui.theme import apply_theme

from ui.api_client import API_BASE, api_get

st.set_page_config(page_title="UML-Pipeline · Settings", layout="wide")
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
    st.info("Mock providers are ON — offline mode without external API keys.")
else:
    st.warning("Live providers enabled — ensure models/API keys are configured.")

ft = health.get("use_finetuned_code") or health.get("finetuned")
adapter = health.get("finetuned_adapter_path")
if ft:
    st.success(f"Fine-tuned PlantUML code model ON · adapter: `{adapter}`")
else:
    st.caption("Fine-tuned code model is OFF. Train with `make finetune`, then set USE_FINETUNED_CODE=true.")

st.markdown(
    """
### Configuration flags (environment)

| Variable | Purpose |
|----------|---------|
| `MOCK_PROVIDERS` | `true` = offline mock (default); `false` = live models |
| `USE_HF_INFERENCE` | Use Hugging Face Inference Providers (Llama + DeepSeek) |
| `HF_TOKEN` | Hugging Face token with Inference Providers permission |
| `SPEC_MODEL` | Spec LLM (default `meta-llama/Llama-3.2-1B-Instruct`) |
| `CODE_MODEL` | Code LLM (default `deepseek-ai/DeepSeek-R1-Distill-Qwen-32B`) |
| `USE_OLLAMA` | Local Ollama instead of HF / OpenAI |
| `PLANTUML_REMOTE` | Use plantuml.com when Java is missing (default true) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Other OpenAI-compatible APIs |
| `DATABASE_URL` | SQLite (default) or Postgres URL |

Copy `.env.example` → `.env`, set `HF_TOKEN`, then `MOCK_PROVIDERS=false` and `USE_HF_INFERENCE=true`. Test with `python scripts/test_hf_models.py`.
"""
)
