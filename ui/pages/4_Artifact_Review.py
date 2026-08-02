import streamlit as st

from ui.theme import apply_theme

from ui.api_client import api_get, api_get_bytes

st.set_page_config(page_title="UML-Pipeline · Artifacts", layout="wide")
apply_theme()
st.title("Artifact Review")

diagram_type = st.selectbox(
    "Filter diagram type",
    ["(all)", "class", "object", "component", "package", "flowchart"],
)
render_status = st.selectbox("Filter render status", ["(all)", "success", "failed", "pending"])
min_score = st.slider("Minimum composite score", 0.0, 6.0, 0.0, 0.1)

params = {}
if diagram_type != "(all)":
    params["diagram_type"] = diagram_type
if render_status != "(all)":
    params["render_status"] = render_status
if min_score > 0:
    params["min_score"] = min_score

try:
    artifacts = api_get("/api/artifacts", **params)
except Exception as exc:
    st.error(exc)
    st.stop()

st.table(artifacts)
ids = [a["id"] for a in artifacts]
if not ids:
    st.info("No artifacts match filters.")
    st.stop()

selected = st.selectbox("Open artifact", ids)
detail = api_get(f"/api/artifacts/{selected}")

st.subheader(f"Artifact #{selected} — {detail['diagram_type']}")
if detail.get("input_mode") == "source_code" or detail.get("source_language"):
    lang = detail.get("source_language") or "unknown"
    st.caption(f"Input mode: `{detail.get('input_mode', 'source_code')}` · detected language: `{lang}`")
    st.code(detail["source_requirement"], language=lang if lang != "unknown" else None)
else:
    st.caption(f"Input mode: `{detail.get('input_mode', 'requirement')}`")
    st.write(detail["source_requirement"])
with st.expander("Technical specification"):
    st.text(detail["technical_spec"])
with st.expander("PlantUML"):
    st.code(detail["plantuml_code"])

c1, c2 = st.columns(2)
c1.metric("Composite score", f"{detail['composite_score']:.3f}")
c2.metric("Render", detail["render_status"])
if detail["render_status"] == "success":
    try:
        st.image(api_get_bytes(f"/api/artifacts/{selected}/image"))
    except Exception as exc:
        st.error(exc)

st.write("**Model scores**")
model_scores = detail.get("model_scores") or []
if model_scores:
    st.dataframe(model_scores, use_container_width=True, hide_index=True)
    for row in model_scores:
        label = f"{row.get('model_name') or row.get('model_key')} · score {row.get('score')}"
        with st.expander(label, expanded=False):
            st.write(row.get("explanation") or "(no explanation returned)")
else:
    st.caption("No per-model scores.")
if detail.get("repair_attempts"):
    st.write("**Repairs**")
    st.table(detail["repair_attempts"])
if detail.get("human_reviews"):
    st.write("**Human reviews**")
    st.table(detail["human_reviews"])
