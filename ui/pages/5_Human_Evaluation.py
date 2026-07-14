from pathlib import Path

import streamlit as st

from ui.theme import apply_theme

from ui.api_client import api_get, api_post

st.set_page_config(page_title="Human Evaluation", layout="wide")
apply_theme()
st.title("Human Evaluation")

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

reviewer_name = st.text_input("Reviewer name", value="Thesis Reviewer")
reviewer_role = st.selectbox("Role", ["expert", "student", "advisor", "author"])

c1, c2 = st.columns(2)
with c1:
    semantic = st.slider("Semantic correctness", 1, 5, 3)
    structural = st.slider("Structural completeness", 1, 5, 3)
with c2:
    syntactic = st.slider("Syntactic accuracy", 1, 5, 3)
    coherence = st.slider("Overall coherence", 1, 5, 3)
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
                "comments": comments,
            },
        )
        st.success(f"Saved review #{out['id']} — mean {out['mean_score']:.2f}")
    except Exception as exc:
        st.error(exc)
