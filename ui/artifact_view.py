"""Shared artifact result UI — diagram first, then PlantUML / spec / scores."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.api_client import api_auth_mismatch_message, api_get_bytes, api_post
from ui.nav import go_eval, go_gallery
from ui.theme import show_image


def vlm_skipped(artifact: dict[str, Any]) -> bool:
    msgs = str(artifact.get("validation_messages") or "")
    if "VLM ensemble skipped" in msgs or "VLM scoring skipped" in msgs:
        return True
    scores = artifact.get("model_scores") or []
    return bool(scores) and all(not s.get("available", True) for s in scores)


def render_score_strip(artifact: dict[str, Any]) -> None:
    skipped = vlm_skipped(artifact)
    render_ok = artifact.get("render_status") == "success"
    composite = float(artifact.get("composite_score") or 0)
    votes = artifact.get("affirmative_votes") or 0
    tau = artifact.get("acceptance_tau") or 4.0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Type", str(artifact.get("diagram_type") or "—"))
    c2.metric("Render", "ok" if render_ok else "failed")
    c3.metric("S", "—" if skipped else f"{composite:.2f}")
    c4.metric("A", "—" if skipped else ("yes" if artifact.get("majority_accepted") else "no"))
    c5.metric("Dataset", "in" if artifact.get("dataset_accepted") else "out")
    if not skipped:
        st.caption(f"Majority {votes}/3 at τ={tau:g} · S ≥ 3 and A=1 to enter the dataset")


def _png(artifact_id: int) -> bytes | None:
    try:
        return api_get_bytes(f"/api/artifacts/{artifact_id}/image")
    except Exception:
        return None


def render_artifact_result(artifact: dict[str, Any], *, key_prefix: str = "art") -> None:
    aid = artifact.get("id")
    render_score_strip(artifact)
    skipped = vlm_skipped(artifact)

    actions = st.columns(3)
    if aid is not None:
        if actions[0].button("Open in gallery", key=f"{key_prefix}-gal-{aid}", use_container_width=True):
            go_gallery(int(aid))
        if actions[1].button("Rate this diagram", key=f"{key_prefix}-rate-{aid}", use_container_width=True):
            go_eval(int(aid))
        if artifact.get("render_status") == "success":
            if actions[2].button("Rescore VLMs", key=f"{key_prefix}-rescore-{aid}", use_container_width=True):
                warn = api_auth_mismatch_message()
                if warn:
                    st.warning(warn)
                try:
                    updated = api_post(f"/api/artifacts/{aid}/rescore", {})
                    st.session_state["last_artifact"] = updated
                    arts = st.session_state.get("last_artifacts") or []
                    st.session_state["last_artifacts"] = [
                        updated if a.get("id") == updated.get("id") else a for a in arts
                    ] or [updated]
                    st.success("Rescored.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    tabs = st.tabs(["Diagram", "PlantUML", "Specification", "VLM scores"])
    with tabs[0]:
        if artifact.get("render_status") == "success" and aid is not None:
            png = _png(int(aid))
            if png:
                show_image(png, caption=f"#{aid} · {artifact.get('diagram_type')}")
                st.download_button(
                    "Download PNG",
                    png,
                    file_name=f"uml-{aid}-{artifact.get('diagram_type')}.png",
                    mime="image/png",
                    key=f"{key_prefix}-png-{aid}",
                )
            else:
                st.warning("Image file is missing.")
        else:
            st.error("Render failed — S is 0. PlantUML is on the next tab.")
    with tabs[1]:
        puml = artifact.get("plantuml_code") or ""
        st.code(puml, language="text")
        st.download_button(
            "Download .puml",
            puml,
            file_name=f"uml-{aid or 'diagram'}.puml",
            key=f"{key_prefix}-puml-{aid}",
        )
    with tabs[2]:
        src_mode = artifact.get("input_mode") or "requirement"
        lang = artifact.get("source_language")
        st.caption(f"Input: `{src_mode}`" + (f" · `{lang}`" if lang else ""))
        src = artifact.get("source_requirement") or ""
        if src_mode == "source_code" or lang:
            st.code(src, language=lang if lang and lang != "unknown" else "text")
        else:
            st.write(src)
        st.markdown("**Technical specification**")
        st.text(artifact.get("technical_spec") or "")
    with tabs[3]:
        scores = artifact.get("model_scores") or []
        if skipped:
            st.info("VLM scoring was skipped for this run.")
        elif scores:
            st.dataframe(scores, use_container_width=True, hide_index=True)
            for row in scores:
                with st.expander(f"{row.get('model_name') or row.get('model_key')} · {row.get('score')}"):
                    st.write(row.get("explanation") or "(no explanation)")
        else:
            st.info("No VLM scores stored.")
        repairs = artifact.get("repair_attempts") or []
        if repairs:
            st.markdown("**Repairs**")
            st.dataframe(repairs, use_container_width=True, hide_index=True)
        notes = artifact.get("validation_messages") or ""
        if notes:
            with st.expander("Validation notes"):
                st.text(notes)


def render_artifact_grid(artifacts: list[dict[str, Any]], *, key_prefix: str = "grid") -> None:
    if not artifacts:
        return
    cols = st.columns(min(4, len(artifacts)))
    for i, art in enumerate(artifacts):
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.markdown(f"**#{art.get('id')} · {art.get('diagram_type')}**")
                skipped = vlm_skipped(art)
                s = "—" if skipped else f"{float(art.get('composite_score') or 0):.2f}"
                st.caption(f"S {s} · A {'yes' if art.get('majority_accepted') else 'no'}")
                if art.get("render_status") == "success" and art.get("id") is not None:
                    png = _png(int(art["id"]))
                    if png:
                        show_image(png)
                if art.get("id") is not None:
                    if st.button("Open", key=f"{key_prefix}-open-{art['id']}", use_container_width=True):
                        go_gallery(int(art["id"]))
