from pathlib import Path

import streamlit as st

from ui.api_client import api_get, api_get_bytes, api_post
from ui.nav import go_gallery
from ui.theme import apply_theme, show_image

st.set_page_config(page_title="UML-Pipeline · Evaluation", layout="wide")
apply_theme()
st.title("Human Evaluation")
st.caption("Rate 0–6 on the same scale as the VLMs.")

rubric_path = Path(__file__).resolve().parents[2] / "prompts" / "human_evaluation_rubric.v1.txt"
if rubric_path.is_file():
    with st.expander("Rubric"):
        st.write(rubric_path.read_text(encoding="utf-8"))

try:
    artifacts = api_get("/api/artifacts", limit=200)
except Exception as exc:
    st.error(exc)
    st.stop()

if not artifacts:
    st.warning("Generate a diagram first.")
    st.stop()

options = {f"#{a['id']} [{a['diagram_type']}] S={a['composite_score']:.2f}": a["id"] for a in artifacts}
ids = list(options.values())
labels = list(options.keys())
preferred = st.session_state.get("eval_artifact_id") or st.session_state.get("gallery_selected")
index = ids.index(int(preferred)) if preferred is not None and int(preferred) in ids else 0
label = st.selectbox("Artifact", labels, index=index)
artifact_id = options[label]
st.session_state["eval_artifact_id"] = artifact_id

detail = api_get(f"/api/artifacts/{artifact_id}")
st.write((detail.get("source_requirement") or "")[:500])
c_img, c_meta = st.columns([1.15, 0.85])
with c_img:
    if detail.get("render_status") == "success":
        try:
            show_image(api_get_bytes(f"/api/artifacts/{artifact_id}/image"), caption=f"#{artifact_id}")
        except Exception as exc:
            st.caption(f"Image unavailable: {exc}")
    else:
        st.warning("No render — score from PlantUML.")
        st.code(detail.get("plantuml_code") or "", language="text")
with c_meta:
    vlm_s = float(detail.get("composite_score") or 0)
    st.metric("VLM S", f"{vlm_s:.2f}")
    st.metric("Majority A", "yes" if detail.get("majority_accepted") else "no")
    st.caption("Dataset: " + ("in" if detail.get("dataset_accepted") else "out"))
    if st.button("Open in gallery", use_container_width=True):
        go_gallery(artifact_id)
    with st.expander("PlantUML"):
        st.code(detail.get("plantuml_code") or "", language="text")

existing = detail.get("human_reviews") or []
if existing:
    st.markdown("**Saved reviews**")
    st.dataframe(
        [
            {
                "reviewer": r.get("reviewer_name"),
                "mean": r.get("mean_score"),
                "semantic": r.get("semantic_correctness"),
                "structural": r.get("structural_completeness"),
                "syntactic": r.get("syntactic_accuracy"),
                "coherence": r.get("overall_coherence"),
            }
            for r in existing
        ],
        use_container_width=True,
        hide_index=True,
    )

reviewer_name = st.text_input("Reviewer name", value=st.session_state.get("reviewer_name") or "Reviewer")
st.session_state["reviewer_name"] = reviewer_name
reviewer_role = st.selectbox("Role", ["expert", "student", "advisor", "author"])

c1, c2 = st.columns(2)
with c1:
    semantic = st.slider("Semantic correctness", 0, 6, 4)
    structural = st.slider("Structural completeness", 0, 6, 4)
with c2:
    syntactic = st.slider("Syntactic accuracy", 0, 6, 4)
    coherence = st.slider("Overall coherence", 0, 6, 4)
comments = st.text_area("Comments")
human_mean = (semantic + structural + syntactic + coherence) / 4.0
st.caption(f"Your mean: **{human_mean:.2f}** / 6 · VLM S: **{vlm_s:.2f}** · Δ {human_mean - vlm_s:+.2f}")

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
        st.success(
            f"Saved review #{out['id']} — human {out['mean_score']:.2f} vs VLM S {vlm_s:.2f}"
        )
        st.rerun()
    except Exception as exc:
        st.error(exc)
