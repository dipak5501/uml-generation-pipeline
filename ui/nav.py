"""In-app page jumps (Streamlit 1.39+)."""

from __future__ import annotations

import streamlit as st


def go_generate() -> None:
    st.switch_page("pages/2_Single_Generation.py")


def go_gallery(artifact_id: int | None = None) -> None:
    if artifact_id is not None:
        st.session_state["gallery_selected"] = int(artifact_id)
    st.switch_page("pages/4_Generated_Diagrams.py")


def go_eval(artifact_id: int | None = None) -> None:
    if artifact_id is not None:
        st.session_state["eval_artifact_id"] = int(artifact_id)
        st.session_state["gallery_selected"] = int(artifact_id)
    st.switch_page("pages/5_Human_Evaluation.py")


def go_analytics() -> None:
    st.switch_page("pages/6_Analytics.py")
