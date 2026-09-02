from pathlib import Path

import streamlit as st

from ui.theme import apply_theme, show_image

from ui.api_client import api_get, api_get_bytes, api_post

st.set_page_config(page_title="UML-Pipeline · Evaluation", layout="wide")
apply_theme()
st.title("Human Evaluation")
st.caption("0–6 integer scale, identical to the VLM rubric in the thesis. This server is the Mac Studio.")

rubric_path = Path(__file__).resolve().parents[2] / "prompts" / "human_evaluation_rubric.v1.txt"
if rubric_path.is_file():
    st.info(rubric_path.read_text(encoding="utf-8"))

try:
    artifacts = api_get("/api/artifacts")
except Exception as exc:
    st.error(exc)
    st.stop()

if not artifacts:
    st.warning("No artifacts to review yet.")
    st.stop()

options = {f"#{a['id']} [{a['diagram_type']}] score={a['composite_score']:.2f}": a["id"] for a in artifacts}
label = st.selectbox("Artifact", list(options.keys()))
artifact_id = options[label]

detail = api_get(f"/api/artifacts/{artifact_id}")
st.write(detail["source_requirement"][:500])
c_img, c_meta = st.columns([1.1, 0.9])
with c_img:
    if detail.get("render_status") == "success":
        try:
            show_image(api_get_bytes(f"/api/artifacts/{artifact_id}/image"), caption=f"Artifact #{artifact_id}")
        except Exception as exc:
            st.caption(f"Image unavailable: {exc}")
    else:
        st.warning("Render failed — score the PlantUML/spec, or pick another artifact.")
with c_meta:
    st.metric("VLM composite S", f"{detail.get('composite_score', 0):.2f}")
    st.metric("Majority A", "yes" if detail.get("majority_accepted") else "no")
    st.caption(f"Dataset gate: {'accepted' if detail.get('dataset_accepted') else 'rejected'}")
    with st.expander("PlantUML"):
        st.code(detail.get("plantuml_code") or "", language="text")

reviewer_name = st.text_input("Reviewer name", value="Reviewer")
reviewer_role = st.selectbox("Role", ["expert", "student", "advisor", "author"])

c1, c2 = st.columns(2)
with c1:
    semantic = st.slider("Semantic correctness", 0, 6, 4)
    structural = st.slider("Structural completeness", 0, 6, 4)
with c2:
    syntactic = st.slider("Syntactic accuracy", 0, 6, 4)
    coherence = st.slider("Overall coherence", 0, 6, 4)
comments = st.text_area("Comments")

if st.button("Save evaluation", type="primary"):
    try:
        out = api_post(
            "/api/human-review",
            {
                "artifact_id": artifact_id,
                "reviewer_name": reviewer_name,
                "reviewer_role": reviewer_role,
                "semantic_correctness": semantic,
                "structural_completeness": structural,
                "syntactic_accuracy": syntactic,
                "overall_coherence": coherence,
                "score_scale": 6,
                "comments": comments,
            },
        )
        st.success(f"Saved review #{out['id']} — mean {out['mean_score']:.2f} / 6")
    except Exception as exc:
        st.error(exc)
