"""UML-Pipeline — Streamlit home."""

from __future__ import annotations

import streamlit as st

from ui.api_client import API_BASE, api_auth_mismatch_message, api_get, api_get_bytes
from ui.nav import go_eval, go_gallery, go_generate
from ui.theme import apply_theme, footer, hero, show_image, stats_row

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
    "From requirements to verified UML",
    "Generate, inspect, and rate class / object / component / package diagrams.",
    chips=["Mac Studio", "PlantUML", "3 VLMs"],
)

if not live:
    st.error(f"API offline at `{API_BASE}`. {_api_error or ''}")
    footer()
    st.stop()

assert health is not None and summary is not None
stats_row(
    [
        ("Artifacts", str(summary.get("total_artifacts", 0))),
        ("Dataset in", str(summary.get("dataset_accepted_count", 0))),
        ("Majority OK", str(summary.get("majority_accepted_count", 0))),
        ("Provider", str(health.get("provider_summary") or health.get("provider", "?")).upper()),
    ]
)

_auth_warn = api_auth_mismatch_message()
if _auth_warn:
    st.warning(_auth_warn)

b1, b2, b3 = st.columns(3)
if b1.button("Generate", type="primary", use_container_width=True):
    go_generate()
if b2.button("Diagrams", use_container_width=True):
    go_gallery()
if b3.button("Rate diagrams", use_container_width=True):
    go_eval()

st.subheader("Recent")
try:
    recent = api_get("/api/artifacts", limit=6) or []
except Exception:
    recent = []
if not recent:
    st.info("Nothing stored yet. Generate a diagram.")
else:
    cols = st.columns(3)
    for i, art in enumerate(recent[:6]):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**#{art['id']} · {art['diagram_type']}**")
                st.caption(f"S {float(art.get('composite_score') or 0):.2f}")
                if art.get("render_status") == "success":
                    try:
                        show_image(api_get_bytes(f"/api/artifacts/{art['id']}/image"))
                    except Exception:
                        pass
                a1, a2 = st.columns(2)
                if a1.button("Open", key=f"home-open-{art['id']}", use_container_width=True):
                    go_gallery(art["id"])
                if a2.button("Rate", key=f"home-rate-{art['id']}", use_container_width=True):
                    go_eval(art["id"])

footer()
