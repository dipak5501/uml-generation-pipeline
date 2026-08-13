"""Shared visual theme for UML-Pipeline."""

from __future__ import annotations

import streamlit as st

BRAND = "UML-Pipeline"

# Keep CSS compact — injected once per page.
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --ink: #14212b; --ink-soft: #3a4a57; --accent: #0f766e;
  --line: rgba(20,33,43,0.12); --glow: rgba(15,118,110,0.18);
}
html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; color: var(--ink); }
.stApp {
  background:
    radial-gradient(1100px 520px at 8% -8%, rgba(15,118,110,0.14), transparent 55%),
    linear-gradient(180deg, #f7f3ea 0%, #ebe4d6 55%, #e4ddd0 100%);
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0e1a20 0%, #163038 100%);
  border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * { color: #e8efe9 !important; }
[data-testid="stSidebar"] a { color: #b7d5cf !important; }
[data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {
  content: "UML-Pipeline";
  display: block;
  font-family: "Syne", sans-serif;
  font-weight: 800;
  font-size: 1.15rem;
  letter-spacing: -0.03em;
  color: #f7f3ea !important;
  padding: 0.35rem 0.85rem 0.15rem;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"]::after {
  content: "Automated UML generation";
  display: block;
  font-size: 0.72rem;
  color: #9ec9c2 !important;
  padding: 0 0.85rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 0.6rem;
}
h1, h2, h3 {
  font-family: "Syne", sans-serif !important;
  letter-spacing: -0.02em;
  color: var(--ink) !important;
}
div[data-testid="stTextArea"] textarea {
  border: 1px solid var(--line) !important;
  background: rgba(255,252,246,0.95) !important;
  min-height: 180px;
}
.stButton > button[kind="primary"] {
  font-family: "Syne", sans-serif !important;
  background: var(--accent) !important;
  color: #f7f3ea !important;
  border-color: var(--accent) !important;
  border-radius: 0 !important;
}
"""


def apply_theme(*, live: bool | None = None, show_job_banner: bool = True) -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    left, right = st.columns([3, 1])
    with left:
        st.markdown("### UML-Pipeline")
        st.caption("requirements → PlantUML → verification")
    with right:
        if live is True:
            st.success("System online")
        elif live is False:
            st.warning("System offline")
    if show_job_banner:
        try:
            from ui.jobs import render_active_job_banner

            # On most pages, show status but do not force auto-refresh loops that
            # fight with interactive widgets; Generate page polls more aggressively.
            render_active_job_banner(auto_refresh=False)
        except Exception:
            pass


def hero(
    title: str,
    subtitle: str,
    chips: list[str] | None = None,
    *,
    show_brand: bool = True,
    kicker: str = "Automated UML · Multimodal verification",
) -> None:
    st.caption(kicker)
    if show_brand:
        st.title("UML-Pipeline")
    st.subheader(title)
    st.write(subtitle)
    if chips:
        st.caption(" · ".join(chips))
    st.divider()


def panel(title: str, body: str) -> None:
    # Strip simple HTML tags used by callers (<code>...</code>)
    clean = (
        body.replace("<code>", "`")
        .replace("</code>", "`")
        .replace("<b>", "**")
        .replace("</b>", "**")
    )
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(clean)


def stats_row(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items) or 1)
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)


def footer() -> None:
    st.divider()
    st.caption(
        "UML-Pipeline · Automated UML Dataset Generation from Natural-Language Requirements "
        "with Multimodal Verification for Software Design — Yadav & Zhao"
    )
