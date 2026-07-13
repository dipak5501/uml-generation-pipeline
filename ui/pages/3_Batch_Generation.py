import time

import streamlit as st

from ui.api_client import api_get, api_post

st.set_page_config(page_title="Batch Generation", layout="wide")
st.title("Batch Generation")

n = st.number_input("Number of sample requirements", min_value=1, max_value=20, value=2)
diagram_types = st.multiselect(
    "Diagram types",
    ["class", "object", "component", "package"],
    default=["class", "object", "component", "package"],
)
custom = st.text_area("Optional base requirement (variants will be generated)", value="")

if st.button("Start batch job", type="primary", disabled=not diagram_types):
    payload = {
        "n_samples": int(n),
        "diagram_types": diagram_types,
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
    for _ in range(120):
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
    st.dataframe(arts, use_container_width=True)
    st.markdown("Download dataset: open **Analytics** or call `/api/export/dataset?fmt=jsonl`")
