"""Shared visual theme for the Streamlit thesis demo."""

from __future__ import annotations

import streamlit as st

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

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #122028 0%, #1a3038 100%);
  border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * { color: #e8efe9 !important; }
[data-testid="stSidebar"] a { color: #b7d5cf !important; }

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
    linear-gradient(135deg, rgba(20,33,43,0.94) 0%, rgba(18,52,55,0.92) 55%, rgba(15,118,110,0.85) 100%);
  color: #f7f3ea;
  padding: 2.4rem 2.2rem 2rem;
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
  margin-bottom: 0.7rem;
}
.hero h1 {
  color: #f7f3ea !important;
  font-size: clamp(1.8rem, 3vw, 2.6rem);
  line-height: 1.08;
  margin: 0 0 0.75rem;
  max-width: 18ch;
}
.hero p {
  margin: 0;
  max-width: 52ch;
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}
.nav-card {
  border: 1px solid var(--line);
  background: rgba(255,252,246,0.9);
  padding: 1rem;
  min-height: 7.2rem;
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

@media (max-width: 900px) {
  .stat-grid, .nav-cards { grid-template-columns: 1fr 1fr; }
  .hero { padding: 1.6rem 1.2rem; }
}
@media (max-width: 640px) {
  .stat-grid, .nav-cards { grid-template-columns: 1fr; }
}
"""


def apply_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str, chips: list[str] | None = None) -> None:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in (chips or []))
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-kicker">UML · Multimodal Verification · Thesis Demo</div>
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
