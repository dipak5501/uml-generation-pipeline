import streamlit as st

from ui.api_client import api_get, api_post
from ui.jobs import active_job_id, clear_job, fetch_job, render_active_job_banner, track_job
from ui.theme import apply_theme

st.set_page_config(page_title="UML-Pipeline · Batch", layout="wide")
apply_theme(show_job_banner=False)
st.title("Batch Generation")
st.markdown(
    "Generate a large evaluation dataset from built-in sample sentences "
    "(50 requirements × 4 diagram types = **200 artifacts**). "
    "Jobs run in the background — you can leave this page while they finish."
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
    ["class", "object", "component", "package"],
    default=["class", "object", "component", "package"],
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

busy = False
jid = active_job_id()
if jid is not None:
    j = fetch_job(jid)
    busy = bool(j and j.get("status") in ("pending", "running"))

if st.button("Start batch job", type="primary", disabled=not diagram_types or busy):
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
        st.success(f"Started job #{job['id']} — total units: {job['total']}")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

job = render_active_job_banner(auto_refresh=False)
if job and job.get("status") in ("pending", "running"):
    st.progress(min(0.99, (job.get("completed") or 0) / max(job.get("total") or 1, 1)))
    if st.button("Refresh progress"):
        st.rerun()
    # Soft auto-refresh while on this page only
    import time

    time.sleep(2.0)
    st.rerun()
elif job and job.get("status") == "completed":
    st.success("Batch completed")
    clear_job()
elif job and job.get("status") == "failed":
    clear_job()

st.subheader("Artifacts")
try:
    arts = api_get("/api/artifacts")
    st.metric("Total artifacts now", len(arts))
    st.table(arts[:100])
except Exception as exc:
    st.error(exc)
st.markdown("Download dataset from **Analytics** or `/api/export/dataset?fmt=jsonl`")
