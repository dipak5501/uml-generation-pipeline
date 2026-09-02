import streamlit as st

from ui.theme import apply_theme

from ui.api_client import API_BASE, api_get

st.set_page_config(page_title="UML-Pipeline · Settings", layout="wide")
apply_theme()
st.title("Settings")
st.caption(f"API `{API_BASE}`")

try:
    health = api_get("/api/settings/health")
    summary = api_get("/api/analytics/summary")
except Exception as exc:
    st.error(f"Health check failed: {exc}")
    st.stop()

status = health.get("status") or "unknown"
if status == "ok":
    st.success("API healthy")
else:
    st.warning(f"API status: {status}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Provider", str(health.get("provider_summary") or health.get("provider") or "—"))
c2.metric("Artifacts", summary.get("total_artifacts", 0))
c3.metric("Render fails", summary.get("render_failures", 0))
c4.metric("Mean S", f"{(summary.get('mean_composite') or 0):.2f}")

flags = st.columns(3)
with flags[0]:
    if health.get("java_available"):
        st.success("Java · local PlantUML jar")
    else:
        st.info("No local Java · remote PlantUML")
with flags[1]:
    if health.get("mock_providers"):
        st.info("Mock providers")
    else:
        st.success("Live models")
with flags[2]:
    if health.get("use_finetuned_code") and health.get("finetuned_adapter_present"):
        st.success("LoRA adapter present")
    elif health.get("use_finetuned_code"):
        st.warning("LoRA enabled but adapter missing")
    else:
        st.caption("LoRA off")

msgs = health.get("messages") or []
if msgs:
    with st.expander("Health details"):
        for m in msgs:
            st.write(f"- {m}")

try:
    adapt = api_get("/api/adaptation/status")
except Exception:
    adapt = None

if adapt and (adapt.get("generators") or adapt.get("recent")):
    st.subheader("Adaptation")
    gens = adapt.get("generators") or {}
    if gens:
        rows = [
            {"type": dt, "generator": name, **cell}
            for dt, cells in gens.items()
            for name, cell in cells.items()
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    recent = adapt.get("recent") or []
    if recent:
        st.dataframe(list(reversed(recent))[:20], use_container_width=True, hide_index=True)
