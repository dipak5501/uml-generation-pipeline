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

try:
    adapt = api_get("/api/adaptation/status")
except Exception:
    adapt = None

if adapt:
    st.subheader("Self-adaptation memory")
    st.caption(
        "The pipeline records which generator and repair strategy succeeded for each "
        "diagram type, then prefers winners on later runs instead of repeating the same prompt."
    )
    st.caption(f"Updated: `{adapt.get('updated_at') or 'no runs yet'}`")
    gens = adapt.get("generators") or {}
    if gens:
        rows = []
        for dtype, cells in gens.items():
            for name, cell in cells.items():
                rows.append(
                    {
                        "diagram_type": dtype,
                        "generator": name,
                        "ok": cell.get("ok"),
                        "fail": cell.get("fail"),
                        "n": cell.get("n"),
                        "rate": cell.get("rate"),
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    strats = adapt.get("strategies") or {}
    if strats:
        srows = []
        for key, cells in strats.items():
            for name, cell in cells.items():
                srows.append(
                    {
                        "key": key,
                        "strategy": name,
                        "ok": cell.get("ok"),
                        "fail": cell.get("fail"),
                        "rate": cell.get("rate"),
                    }
                )
        st.dataframe(srows, use_container_width=True, hide_index=True)
    recent = adapt.get("recent") or []
    if recent:
        st.markdown("**Recent adaptation events**")
        st.dataframe(list(reversed(recent)), use_container_width=True, hide_index=True)

st.markdown(
    """
### Configuration flags (environment)

| Variable | Purpose |
|----------|---------|
| `MOCK_PROVIDERS` | `true` = offline mock (default); `false` = live models |
| `USE_OLLAMA` | Local Ollama (free) for spec / VLM / code fallback |
| `USE_FINETUNED_CODE` | Local MLX LoRA for PlantUML (`uml-plantuml-lora-sourcecode-30k` in production) |
| `FINETUNED_ADAPTER_PATH` | LoRA adapter directory (production: `models/uml-plantuml-lora-sourcecode-30k`) |
| `API_ACCESS_TOKEN` | Required for public deploy / remote agent (`/api/agent`) |
| `USE_HF_INFERENCE` | Hugging Face Inference Providers (paid/credits for many models) |
| `HF_TOKEN` | Hugging Face token (only if using HF) |
| `SPEC_MODEL` | Spec LLM (default `meta-llama/Llama-3.2-1B-Instruct` → Ollama `llama3.2:1b`) |
| `CODE_MODEL` | Code LLM fallback (DeepSeek 32B rarely local; falls back to spec model) |
| `VLM_MODELS` | Vision scorers (Ollama tags; remapped to HF IDs when using HF) |
| `PLANTUML_REMOTE` | Use plantuml.com when Java is missing (default true) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | Other OpenAI-compatible APIs |
| `DATABASE_URL` | SQLite (default) or Postgres URL |

**Recommended local free setup:** `MOCK_PROVIDERS=false`, `USE_OLLAMA=true`, `USE_FINETUNED_CODE=true`, `FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k`, `USE_HF_INFERENCE=false`, `VLM_AYA_BACKEND=local`.  
Start with `make run` (or `./scripts/run_local.sh`). Set `API_ACCESS_TOKEN` before public Cloudflare tunnels.
"""
)
