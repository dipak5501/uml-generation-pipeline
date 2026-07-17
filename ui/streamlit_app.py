"""UML Generation Thesis Demo — Streamlit entry."""

from __future__ import annotations

import streamlit as st

from ui.api_client import API_BASE, api_get
from ui.theme import apply_theme, hero, panel, stats_row

st.set_page_config(
    page_title="UML Multimodal Studio",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

hero(
    "Automated UML Dataset Generation",
    "From natural-language requirements to PlantUML diagrams, multimodal scores, "
    "human review, and analytics — class, object, component, package, and flowchart.",
    chips=["Dipak Yadav · Yutong Zhao", "Design-phase modeling", "PlantUML + VLM ensemble"],
)

try:
    health = api_get("/api/settings/health")
    summary = api_get("/api/analytics/summary")
    stats_row(
        [
            ("Artifacts", str(summary.get("total_artifacts", 0))),
            ("Dataset accepted", str(summary.get("dataset_accepted_count", 0))),
            ("Majority OK", str(summary.get("majority_accepted_count", 0))),
            ("Provider", str(health.get("provider", "?")).upper()),
        ]
    )
    if health.get("status") == "ok":
        st.success(f"Live API connected · {API_BASE}")
    else:
        st.warning(f"API status: {health.get('status')} · {API_BASE}")
except Exception as exc:
    panel(
        "API offline",
        f"Cannot reach {API_BASE}. Start it with <code>make api</code> then refresh. ({exc})",
    )
    st.stop()

st.markdown(
    """
    <div class="nav-cards">
      <div class="nav-card"><strong>Generate</strong><span>Paste any sentence or paragraph and create UML / flowchart diagrams with scores.</span></div>
      <div class="nav-card"><strong>Batch</strong><span>Build demo datasets across diagram types for thesis evaluation.</span></div>
      <div class="nav-card"><strong>Review & analytics</strong><span>Browse artifacts, run human rubrics, and export CSV/JSONL.</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")
c1, c2, c3 = st.columns(3)
with c1:
    panel("1 · Write a requirement", "Use the Generate page. Free text is the main input — examples are optional.")
with c2:
    panel("2 · Pick a diagram", "Class, object, component, package, or flowchart — rendered with PlantUML.")
with c3:
    panel("3 · Inspect quality", "Per-model scores, composite score, repairs, and human review.")

st.caption("Paper: Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design")
