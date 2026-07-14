import time

import streamlit as st

from ui.theme import apply_theme

from ui.api_client import api_get, api_post

st.set_page_config(page_title="Batch Generation", layout="wide")
apply_theme()
st.title("Batch Generation")
st.markdown(
    "Generate a large demo dataset from built-in sample sentences "
    "(50 requirements × 4 diagram types = **200 artifacts**)."
)

n = st.number_input(
    "Number of sample requirements",
    min_value=1,
    max_value=200,
    value=50,
    help="Each requirement is generated for every selected diagram type.",
)
diagram_types = st.multiselect(
    "Diagram types",
    ["class", "object", "component", "package", "flowchart"],
    default=["class", "object", "component", "package", "flowchart"],
)
custom = st.text_area(
    "Optional: one custom sentence (creates n variants instead of the sample file)",
    value="",
    placeholder="Leave empty to use sample_data/requirements.txt",
)
use_samples = st.checkbox("Use built-in sample file when no custom sentence", value=True)

preview = st.button("Preview sample sentences")
if preview:
    try:
        data = api_get("/api/samples", limit=min(int(n), 20))
        st.write(data.get("requirements") or [])
    except Exception as exc:
        st.error(exc)

est = int(n) * max(len(diagram_types), 1)
st.info(f"Estimated artifacts in this run: **{est}**")

if st.button("Start batch job", type="primary", disabled=not diagram_types):
    payload = {
        "n_samples": int(n),
        "diagram_types": diagram_types,
        "use_sample_file": use_samples,
    }
    if custom.strip():
        payload["requirement"] = custom.strip()
    try:
        job = api_post("/api/generate/batch", payload)
        st.session_state["batch_job_id"] = job["id"]
        st.success(f"Started job #{job['id']} — total units: {job['total']}")
    except Exception as exc:
        st.error(str(exc))

job_id = st.session_state.get("batch_job_id")
if job_id:
    placeholder = st.empty()
    # Allow long runs (200+ artifacts)
    for _ in range(3600):
        job = api_get(f"/api/jobs/{job_id}")
        placeholder.info(
            f"Job {job_id}: {job['status']} — {job['completed']}/{job['total']}"
        )
        if job["status"] in ("completed", "failed"):
            if job["status"] == "failed":
                st.error(job.get("error") or "Batch failed")
            else:
                st.success("Batch completed")
            break
        time.sleep(1.0)

    st.subheader("Artifacts")
    arts = api_get("/api/artifacts")
    st.metric("Total artifacts now", len(arts))
    st.dataframe(arts[:100], use_container_width=True)
    st.markdown("Download dataset from **Analytics** or `/api/export/dataset?fmt=jsonl`")
