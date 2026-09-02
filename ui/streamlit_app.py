"""UML-Pipeline — Streamlit entry."""

from __future__ import annotations

import streamlit as st

from ui.api_client import API_BASE, api_auth_mismatch_message, api_get
from ui.theme import apply_theme, footer, hero, panel, stats_row

st.set_page_config(
    page_title="UML-Pipeline",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

live = None
health = None
summary = None
try:
    health = api_get("/api/settings/health")
    summary = api_get("/api/analytics/summary")
    live = health.get("status") == "ok"
except Exception as exc:
    live = False
    _api_error = str(exc)
else:
    _api_error = None

apply_theme(live=live)

hero(
    "From requirements to verified UML diagrams",
    "Generate class, object, component, and package diagrams from natural "
    "language or source code — with PlantUML rendering, multimodal scores, and dataset gating.",
    chips=["Mac Studio server", "Dipak Yadav · Yutong Zhao", "PlantUML + VLM ensemble"],
)

if live and health and summary:
    stats_row(
        [
            ("Artifacts", str(summary.get("total_artifacts", 0))),
            ("Dataset accepted", str(summary.get("dataset_accepted_count", 0))),
            ("Majority OK", str(summary.get("majority_accepted_count", 0))),
            ("Provider", str(health.get("provider_summary") or health.get("provider", "?")).upper()),
        ]
    )
    st.success(f"Connected · {API_BASE}")
elif not live:
    panel(
        "API offline",
        f"Cannot reach API at <code>{API_BASE}</code>. "
        f"{('Details: ' + _api_error) if _api_error else 'Start the API, then refresh.'}",
    )
    footer()
    st.stop()

_auth_warn = api_auth_mismatch_message()
if _auth_warn:
    st.warning(_auth_warn)

n1, n2, n3, n4 = st.columns(4)
with n1:
    panel("Thesis defense", "Committee tour: paper vs this Mac Studio, RQ demos, package failures, take-home snapshot.")
with n2:
    panel("Generate", "Turn a requirement or source file into a scored UML diagram.")
with n3:
    panel("Generated diagrams", "Browse every previously generated UML image, PlantUML file, and score.")
with n4:
    panel("System design", "Architecture: pipeline stages, providers, verification, and storage.")

c1, c2, c3 = st.columns(3)
with c1:
    panel("1 · Write a requirement", "Open Generate. Free text is the primary input; examples are optional.")
with c2:
    panel("2 · Choose a diagram", "Class, object, component, or package — rendered with PlantUML.")
with c3:
    panel("3 · Inspect quality", "Per-model scores, composite score, repairs, and human review.")

footer()
