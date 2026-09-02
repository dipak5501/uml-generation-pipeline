import time

import streamlit as st

from ui.api_client import api_get, api_post
from ui.jobs import active_job_id, clear_job, fetch_job, render_active_job_banner, track_job
from ui.nav import go_gallery
from ui.theme import apply_theme

st.set_page_config(page_title="UML-Pipeline · Batch", layout="wide")
apply_theme(show_job_banner=False)
st.title("Batch Generation")
st.caption("Each sample requirement is generated for every selected diagram type.")

n = st.number_input("Sample requirements", min_value=1, max_value=200, value=10)
diagram_types = st.multiselect(
    "Diagram types",
    ["class", "object", "component", "package"],
    default=["class", "object", "component", "package"],
)
custom = st.text_area("Optional custom sentence (makes n variants)", value="", height=80)
use_samples = st.checkbox("Use built-in samples when empty", value=True)

if st.button("Preview samples"):
    try:
        data = api_get("/api/samples", limit=min(int(n), 20))
        st.write(data.get("requirements") or [])
    except Exception as exc:
        st.error(exc)

est = int(n) * max(len(diagram_types), 1)
st.caption(f"{est} artifacts in this job")

jid = active_job_id()
job_now = fetch_job(jid) if jid is not None else None
busy = bool(job_now and job_now.get("status") in ("pending", "running"))

if st.button("Start batch", type="primary", disabled=not diagram_types or busy):
    payload = {
        "n_samples": int(n),
        "diagram_types": diagram_types,
        "use_sample_file": use_samples,
    }
    if custom.strip():
        payload["requirement"] = custom.strip()
    try:
        job = api_post("/api/generate/batch", payload)
        track_job(job["id"], label="Batch")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

job = render_active_job_banner(auto_refresh=False)
if job and job.get("status") in ("pending", "running"):
    st.progress(min(0.99, (job.get("completed") or 0) / max(job.get("total") or 1, 1)))
    time.sleep(2.0)
    st.rerun()
elif job and job.get("status") == "completed":
    st.success("Batch finished")
    if st.button("Open diagrams"):
        clear_job()
        go_gallery()
    if st.button("Dismiss"):
        clear_job()
        st.rerun()
elif job and job.get("status") == "failed":
    st.error(job.get("error") or "Batch failed")
    if st.button("Dismiss failed job"):
        clear_job()
        st.rerun()

try:
    summary = api_get("/api/analytics/summary")
    st.metric("Artifacts stored", summary.get("total_artifacts", 0))
except Exception as exc:
    st.error(exc)
if st.button("Browse gallery"):
    go_gallery()
