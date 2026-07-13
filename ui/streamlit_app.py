"""UML Generation Thesis Demo — Streamlit entry."""

from __future__ import annotations

import streamlit as st

from ui.api_client import API_BASE, api_get

st.set_page_config(
    page_title="UML Generation Thesis Demo",
    page_icon="📐",
    layout="wide",
)

st.title("UML Generation Thesis Demo")
st.caption(
    "Automated UML Dataset Generation from Natural-Language Requirements "
    "with Multimodal Verification for Software Design — "
    "class, object, component, and package diagrams."
)

st.markdown(
    """
Use the sidebar pages:

1. **Dashboard** — project summary  
2. **Single Generation** — requirement → full artifact trace  
3. **Batch Generation** — demo dataset jobs  
4. **Artifact Review** — browse and filter  
5. **Human Evaluation** — rubric scoring  
6. **Analytics** — distributions and failures  
7. **Settings** — providers and health  

Start the API first: `uvicorn app.main:app --reload --port 8000`
"""
)

try:
    health = api_get("/api/settings/health")
    summary = api_get("/api/analytics/summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Artifacts", summary.get("total_artifacts", 0))
    col2.metric("Mean score", f"{(summary.get('mean_composite') or 0):.2f}")
    col3.metric("Render failures", summary.get("render_failures", 0))
    col4.metric("Provider", health.get("provider", "?"))
    st.success(f"API connected at {API_BASE} — status: {health.get('status')}")
    if health.get("messages"):
        for m in health["messages"]:
            st.info(m)
except Exception as exc:
    st.error(
        f"Cannot reach API at {API_BASE}. Start it with:\n\n"
        "`make api` or `uvicorn app.main:app --reload --port 8000`\n\n"
        f"Details: {exc}"
    )
