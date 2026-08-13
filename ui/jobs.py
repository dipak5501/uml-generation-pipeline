"""Cross-page generation job tracking for Streamlit."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from ui.api_client import api_get

ACTIVE_JOB_KEY = "active_gen_job_id"
ACTIVE_JOB_META_KEY = "active_gen_job_meta"


def track_job(job_id: int, *, label: str = "Generation") -> None:
    st.session_state[ACTIVE_JOB_KEY] = int(job_id)
    st.session_state[ACTIVE_JOB_META_KEY] = {"label": label, "started": time.time()}


def clear_job() -> None:
    st.session_state.pop(ACTIVE_JOB_KEY, None)
    st.session_state.pop(ACTIVE_JOB_META_KEY, None)


def active_job_id() -> int | None:
    raw = st.session_state.get(ACTIVE_JOB_KEY)
    return int(raw) if raw is not None else None


def fetch_job(job_id: int) -> dict[str, Any] | None:
    try:
        return api_get(f"/api/jobs/{job_id}")
    except Exception:
        return None


def fetch_job_artifacts(job_id: int) -> list[dict[str, Any]]:
    try:
        data = api_get(f"/api/jobs/{job_id}/artifacts")
        return list(data or [])
    except Exception:
        return []


def render_active_job_banner(*, auto_refresh: bool = True) -> dict[str, Any] | None:
    """Show running-job status on every page; keep polling via short reruns."""
    job_id = active_job_id()
    if job_id is None:
        return None

    job = fetch_job(job_id)
    meta = st.session_state.get(ACTIVE_JOB_META_KEY) or {}
    label = meta.get("label") or "Generation"

    if job is None:
        st.warning(
            f"{label} job #{job_id}: status unavailable (API offline?). "
            "Job keeps running on the server."
        )
        c1, c2 = st.columns(2)
        if c1.button("Retry status check", key=f"job_retry_{job_id}"):
            st.rerun()
        if c2.button("Dismiss job banner", key=f"job_dismiss_{job_id}"):
            clear_job()
            st.rerun()
        return None

    status = job.get("status") or "unknown"
    done = int(job.get("completed") or 0)
    total = int(job.get("total") or 0)
    msg = f"{label} job #{job_id}: **{status}** — {done}/{total} diagram(s)"

    if status in ("pending", "running"):
        st.info(msg + " · You can leave this page; generation continues in the background.")
        if st.button("Refresh job progress", key=f"job_refresh_{job_id}"):
            st.rerun()
        if auto_refresh:
            time.sleep(2.0)
            st.rerun()
        return job

    if status == "failed":
        st.error(msg + f" — {job.get('error') or 'failed'}")
        if st.button("Dismiss", key=f"job_fail_dismiss_{job_id}"):
            clear_job()
            st.rerun()
        return job

    st.success(msg + " · finished. Open **Generate** or **Artifact Review** to inspect results.")
    return job


def load_job_results_into_session(job_id: int) -> list[dict[str, Any]]:
    arts = fetch_job_artifacts(job_id)
    if arts:
        st.session_state["last_artifacts"] = arts
        st.session_state["last_artifact"] = arts[0]
    return arts
