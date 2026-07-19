"""Shared visual theme for UML-Pipeline."""

from __future__ import annotations

import streamlit as st

BRAND = "UML-Pipeline"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --ink: #14212b;
  --ink-soft: #3a4a57;
  --paper: #f3efe6;
  --panel: rgba(255, 252, 246, 0.88);
  --line: rgba(20, 33, 43, 0.12);
  --accent: #0f766e;
  --accent-2: #c45c26;
  --glow: rgba(15, 118, 110, 0.18);
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", sans-serif;
  color: var(--ink);
}

.stApp {
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(15, 118, 110, 0.16), transparent 55%),
    radial-gradient(900px 500px at 100% 0%, rgba(196, 92, 38, 0.12), transparent 50%),
    linear-gradient(180deg, #f7f3ea 0%, #ebe4d6 48%, #e4ddd0 100%);
}

/* Site chrome */
.site-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 0.15rem 1rem;
  margin-bottom: 0.25rem;
  border-bottom: 1px solid var(--line);
  animation: rise 0.45s ease-out;
}
.site-brand {
  display: flex;
  align-items: baseline;
  gap: 0.55rem;
  text-decoration: none;
}
.site-brand .mark {
  font-family: "Syne", sans-serif;
  font-weight: 800;
  font-size: 1.35rem;
  letter-spacing: -0.03em;
  color: var(--ink);
}
.site-brand .mark span {
  color: var(--accent);
}
.site-brand .tag {
  font-size: 0.78rem;
  color: var(--ink-soft);
  letter-spacing: 0.02em;
}
.site-status {
  font-size: 0.78rem;
  color: var(--ink-soft);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.site-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--glow);
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

h1, h2, h3, .brand-title {
  font-family: "Syne", sans-serif !important;
  letter-spacing: -0.02em;
  color: var(--ink) !important;
}

.hero {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(20,33,43,0.96) 0%, rgba(18,52,55,0.93) 50%, rgba(15,118,110,0.88) 100%);
  color: #f7f3ea;
  padding: 2.6rem 2.3rem 2.1rem;
  margin: 0.2rem 0 1.4rem;
  box-shadow: 0 24px 60px rgba(20, 33, 43, 0.18);
  animation: rise 0.7s ease-out;
}
.hero::after {
  content: "";
  position: absolute;
  inset: auto -20% -40% 40%;
  height: 180px;
  background: radial-gradient(circle, rgba(196,92,38,0.35), transparent 70%);
  pointer-events: none;
}
.hero-kicker {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: #9ec9c2;
  margin-bottom: 0.55rem;
}
.hero-brand {
  font-family: "Syne", sans-serif;
  font-weight: 800;
  font-size: clamp(2.4rem, 5vw, 3.4rem);
  letter-spacing: -0.04em;
  line-height: 0.98;
  color: #f7f3ea;
  margin: 0 0 0.85rem;
}
.hero-brand span { color: #5eead4; }
.hero h1 {
  color: #f7f3ea !important;
  font-size: clamp(1.15rem, 2vw, 1.45rem);
  font-weight: 600;
  line-height: 1.25;
  margin: 0 0 0.65rem;
  max-width: 36ch;
  opacity: 0.95;
}
.hero p {
  margin: 0;
  max-width: 54ch;
  color: #d7e3df;
  font-size: 1.02rem;
  line-height: 1.55;
}
.hero-meta {
  margin-top: 1.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.7rem;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(255,255,255,0.06);
  color: #e8f2ef;
  font-size: 0.82rem;
}

.panel {
  border: 1px solid var(--line);
  background: var(--panel);
  backdrop-filter: blur(8px);
  padding: 1.15rem 1.2rem 1.05rem;
  margin-bottom: 1rem;
  animation: rise 0.55s ease-out;
}
.panel h3 {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
}
.panel p {
  margin: 0;
  color: var(--ink-soft);
  font-size: 0.95rem;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin: 0.4rem 0 1.2rem;
}
.stat {
  border: 1px solid var(--line);
  background: rgba(255,252,246,0.92);
  padding: 1rem 1rem 0.9rem;
  box-shadow: 0 10px 30px rgba(20,33,43,0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(20,33,43,0.09);
}
.stat .label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
}
.stat .value {
  font-family: "Syne", sans-serif;
  font-size: 1.7rem;
  margin-top: 0.25rem;
  color: var(--ink);
}

.nav-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.8rem;
}
.nav-card {
  border: 1px solid var(--line);
  background: rgba(255,252,246,0.9);
  padding: 1rem;
  min-height: 7.2rem;
  transition: transform 0.2s ease, border-color 0.2s ease;
}
.nav-card:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.45);
}
.nav-card strong {
  display: block;
  font-family: "Syne", sans-serif;
  font-size: 1.02rem;
  margin-bottom: 0.35rem;
}
.nav-card span {
  color: var(--ink-soft);
  font-size: 0.9rem;
  line-height: 1.4;
}

.site-footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 0.85rem;
}
.site-footer strong {
  font-family: "Syne", sans-serif;
  color: var(--ink);
}

div[data-testid="stTextArea"] textarea {
  border: 1px solid var(--line) !important;
  background: rgba(255,252,246,0.95) !important;
  font-family: "IBM Plex Sans", sans-serif !important;
  font-size: 1rem !important;
  line-height: 1.5 !important;
  min-height: 180px;
}
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--glow) !important;
}

.stButton > button[kind="primary"],
.stButton > button {
  font-family: "Syne", sans-serif !important;
  border-radius: 0 !important;
  border: 1px solid var(--ink) !important;
  transition: transform 0.15s ease, background 0.15s ease !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: #f7f3ea !important;
  border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover {
  background: #0b5f59 !important;
  transform: translateY(-1px);
}

code, pre, .stCodeBlock {
  font-family: "IBM Plex Mono", monospace !important;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1100px) {
  .nav-cards { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 900px) {
  .stat-grid { grid-template-columns: 1fr 1fr; }
  .hero { padding: 1.6rem 1.2rem; }
}
@media (max-width: 640px) {
  .stat-grid, .nav-cards { grid-template-columns: 1fr; }
  .site-top { flex-direction: column; align-items: flex-start; }
}
"""


def apply_theme(*, live: bool | None = None) -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    status = ""
    if live is True:
        status = (
            '<div class="site-status"><span class="dot"></span> System online</div>'
        )
    elif live is False:
        status = '<div class="site-status">System offline</div>'
    st.markdown(
        f"""
        <div class="site-top">
          <div class="site-brand">
            <div class="mark">UML<span>-Pipeline</span></div>
            <div class="tag">requirements → PlantUML → verification</div>
          </div>
          {status}
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(
    title: str,
    subtitle: str,
    chips: list[str] | None = None,
    *,
    show_brand: bool = True,
    kicker: str = "Automated UML · Multimodal verification",
) -> None:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in (chips or []))
    brand_html = (
        '<div class="hero-brand">UML<span>-Pipeline</span></div>' if show_brand else ""
    )
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-kicker">{kicker}</div>
          {brand_html}
          <h1>{title}</h1>
          <p>{subtitle}</p>
          <div class="hero-meta">{chip_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel(title: str, body: str) -> None:
    st.markdown(
        f'<div class="panel"><h3>{title}</h3><p>{body}</p></div>',
        unsafe_allow_html=True,
    )


def stats_row(items: list[tuple[str, str]]) -> None:
    cells = "".join(
        f'<div class="stat"><div class="label">{k}</div><div class="value">{v}</div></div>'
        for k, v in items
    )
    st.markdown(f'<div class="stat-grid">{cells}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        """
        <div class="site-footer">
          <strong>UML-Pipeline</strong>
          · Automated UML Dataset Generation from Natural-Language Requirements
          with Multimodal Verification for Software Design — Yadav &amp; Zhao
        </div>
        """,
        unsafe_allow_html=True,
    )
