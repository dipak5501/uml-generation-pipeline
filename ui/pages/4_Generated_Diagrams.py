"""Browse every previously generated UML diagram."""

from __future__ import annotations

import streamlit as st

from ui.api_client import api_auth_mismatch_message, api_get, api_get_bytes, api_post
from ui.jobs import (
    active_job_id,
    clear_job,
    fetch_job,
    fetch_job_artifacts,
    track_job,
)
from ui.nav import go_eval
from ui.theme import apply_theme, hero, show_image

st.set_page_config(page_title="UML-Pipeline · Generated Diagrams", layout="wide", page_icon="▦")
apply_theme()

PAGE_SIZE = 6
ALL_TYPES = ["class", "object", "component", "package"]

hero(
    "Generated UML diagrams",
    "Every diagram this application has produced. Open one to rescore it or generate "
    "class, object, component, or package from the same requirement.",
    chips=["History", "Gallery", "All diagram types"],
)

# If a "generate another type" job just finished, open the new diagram.
_job_id = active_job_id()
if _job_id is not None:
    _job = fetch_job(_job_id)
    if _job and _job.get("status") in ("pending", "running"):
        st.info(f"Job #{_job_id}: {_job.get('status')} — {_job.get('completed')}/{_job.get('total')}")
        import time

        time.sleep(2.0)
        st.rerun()
    elif _job and _job.get("status") == "completed":
        arts = fetch_job_artifacts(_job_id)
        clear_job()
        if arts:
            st.session_state["gallery_selected"] = arts[-1]["id"]
            st.session_state["gallery_offset"] = 0
        st.rerun()
    elif _job and _job.get("status") == "failed":
        st.error(_job.get("error") or "Generation failed")
        if st.button("Dismiss failed job", key="gallery-fail-dismiss"):
            clear_job()
            st.rerun()


@st.cache_data(show_spinner=False, ttl=90)
def _diagram_png(artifact_id: int) -> bytes | None:
    try:
        return api_get_bytes(f"/api/artifacts/{artifact_id}/image")
    except Exception:
        return None


def _snippet(text: str, n: int = 140) -> str:
    raw = " ".join((text or "").split())
    return raw if len(raw) <= n else raw[: n - 1] + "…"


f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
with f1:
    query = st.text_input("Search requirements", placeholder="bookstore, hospital, CartService…")
with f2:
    diagram_type = st.selectbox("Diagram type", ["(all)", "class", "object", "component", "package"])
with f3:
    render_status = st.selectbox("Render", ["(all)", "success", "failed", "pending"])
with f4:
    gate = st.selectbox("Acceptance", ["(all)", "dataset accepted", "majority OK", "not accepted"])

filter_key = (query.strip(), diagram_type, render_status, gate)
if st.session_state.get("gallery_filter_key") != filter_key:
    st.session_state["gallery_filter_key"] = filter_key
    st.session_state["gallery_offset"] = 0

params: dict = {"limit": PAGE_SIZE, "offset": int(st.session_state.get("gallery_offset", 0))}
if query.strip():
    params["q"] = query.strip()
if diagram_type != "(all)":
    params["diagram_type"] = diagram_type
if render_status != "(all)":
    params["render_status"] = render_status
if gate == "dataset accepted":
    params["dataset_accepted"] = True
elif gate == "majority OK":
    params["majority_accepted"] = True
elif gate == "not accepted":
    params["dataset_accepted"] = False

try:
    library = api_get("/api/artifacts/library", **params)
except Exception as exc:
    st.error(exc)
    st.stop()

items = library.get("items") or []
total = int(library.get("total") or 0)
offset = int(library.get("offset") or 0)
st.session_state["gallery_offset"] = offset

shown_from = 0 if total == 0 else offset + 1
shown_to = offset + len(items)
st.caption(f"Showing **{shown_from}–{shown_to}** of **{total}** stored diagram(s). Newest first.")

selected_id = st.session_state.get("gallery_selected")
opened = None
if selected_id:
    try:
        opened = api_get(f"/api/artifacts/{selected_id}")
    except Exception:
        opened = None
        st.session_state.pop("gallery_selected", None)

if opened:
    st.subheader(f"#{opened['id']} · {opened['diagram_type']} diagram")
    meta = st.columns(4)
    meta[0].metric("Render", opened.get("render_status") or "—")
    skipped = "VLM ensemble skipped" in str(opened.get("validation_messages") or "") or (
        bool(opened.get("model_scores"))
        and all(not s.get("available", True) for s in (opened.get("model_scores") or []))
    )
    meta[1].metric("Score", "not scored" if skipped else f"{float(opened.get('composite_score') or 0):.2f}")
    meta[2].metric("Dataset", "accepted" if opened.get("dataset_accepted") else "held out")
    meta[3].metric("Majority", "yes" if opened.get("majority_accepted") else "no")
    st.caption(
        f"{opened.get('created_at') or ''} · input `{opened.get('input_mode')}`"
        + (f" · {opened.get('source_language')}" if opened.get("source_language") else "")
    )
    left, right = st.columns([1.15, 1])
    with left:
        if opened.get("render_status") == "success":
            png = _diagram_png(opened["id"])
            if png:
                show_image(png)
                st.download_button(
                    "Download PNG",
                    png,
                    file_name=f"uml-{opened['id']}-{opened['diagram_type']}.png",
                    mime="image/png",
                    key=f"dl-png-{opened['id']}",
                )
            else:
                st.warning("Image file is missing on disk.")
        else:
            st.info("This run did not produce a renderable image.")
        if opened.get("validation_messages"):
            with st.expander("Acceptance / validation notes"):
                st.text(opened["validation_messages"])
    with right:
        st.markdown("**Original requirement**")
        if opened.get("input_mode") == "source_code" or opened.get("source_language"):
            st.code(opened.get("source_requirement") or "", language=opened.get("source_language") or "text")
        else:
            st.write(opened.get("source_requirement") or "")
        with st.expander("How to read this diagram", expanded=True):
            st.markdown(
                "Boxes are parts of the software; labeled arrows explain the relationship. "
                "Use the diagram to track design as you implement and maintain the system."
            )
            st.text((opened.get("technical_spec") or "")[:2000])
        with st.expander("PlantUML", expanded=True):
            st.code(opened.get("plantuml_code") or "", language="text")
            st.download_button(
                "Download .puml",
                opened.get("plantuml_code") or "",
                file_name=f"uml-{opened['id']}-{opened['diagram_type']}.puml",
                key=f"dl-puml-{opened['id']}",
            )
        with st.expander("Technical specification"):
            st.text(opened.get("technical_spec") or "")
        scores = opened.get("model_scores") or []
        if scores:
            st.markdown("**VLM scores**")
            st.dataframe(scores, use_container_width=True, hide_index=True)
        if opened.get("render_status") == "success":
            _auth_warn = api_auth_mismatch_message()
            if _auth_warn:
                st.warning(_auth_warn)
            if st.button("Rescore with VLMs", key=f"gallery-rescore-{opened['id']}"):
                try:
                    updated = api_post(f"/api/artifacts/{opened['id']}/rescore", {})
                    st.session_state["gallery_selected"] = updated["id"]
                    _diagram_png.clear()
                    st.success("VLM scoring finished.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        current_type = str(opened.get("diagram_type") or "class")
        other_types = [t for t in ALL_TYPES if t != current_type]
        st.markdown("**Generate another UML type from this same input**")
        st.caption(
            "Uses the original requirement or source code. The new diagram is stored in this gallery."
        )
        more_types = st.multiselect(
            "Diagram type(s) to add",
            other_types,
            default=[],
            key=f"more-types-{opened['id']}",
        )
        more_vlm = st.checkbox(
            "Score with all 3 VLMs (Qwen, LLaMA-Vision, Aya)",
            value=True,
            key=f"more-vlm-{opened['id']}",
        )
        if st.button("Rate this diagram", key=f"gallery-rate-{opened['id']}", use_container_width=True):
            go_eval(opened["id"])
        busy = active_job_id() is not None
        if st.button(
            "Generate selected type(s)",
            type="primary",
            disabled=not more_types or busy,
            key=f"more-go-{opened['id']}",
            use_container_width=True,
        ):
            try:
                result = api_post(
                    "/api/generate",
                    {
                        "requirement": opened.get("source_requirement") or "",
                        "diagram_type": more_types[0],
                        "diagram_types": more_types,
                        "input_mode": opened.get("input_mode") or "requirement",
                        "async_mode": True,
                        "skip_vlm": not more_vlm,
                    },
                )
                track_job(int(result["job_id"]), label="Generate other UML type")
                st.success(
                    f"Started job #{result['job_id']} for {', '.join(more_types)}. "
                    "Stay on this page or come back — the new diagram will appear here."
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if st.button("Close detail", key="close-gallery-detail"):
        st.session_state.pop("gallery_selected", None)
        st.rerun()
    st.divider()

if total == 0:
    st.info("No generated diagrams yet. Open **Generate** (or Batch) and create one — it will appear here.")
    st.stop()

cols = st.columns(3)
for i, art in enumerate(items):
    with cols[i % 3]:
        with st.container(border=True):
            label = f"#{art['id']} · {art['diagram_type']}"
            st.markdown(f"**{label}**")
            st.caption(_snippet(art.get("source_requirement") or "", 110))
            if art.get("has_image") and art.get("render_status") == "success":
                png = _diagram_png(art["id"])
                if png:
                    show_image(png)
                else:
                    st.caption("Image missing")
            else:
                st.caption(f"No image ({art.get('render_status')})")
            bits = [
                f"S {float(art.get('composite_score') or 0):.2f}",
                "A yes" if art.get("majority_accepted") else "A no",
                "dataset" if art.get("dataset_accepted") else "held out",
            ]
            if art.get("created_at"):
                bits.append(str(art["created_at"]).replace("T", " ")[:16])
            st.caption(" · ".join(bits))
            o1, o2 = st.columns(2)
            if o1.button("Open", key=f"open-{art['id']}", use_container_width=True):
                st.session_state["gallery_selected"] = art["id"]
                st.rerun()
            if o2.button("Rate", key=f"rate-{art['id']}", use_container_width=True):
                go_eval(art["id"])

nav1, nav2, nav3 = st.columns([1, 2, 1])
with nav1:
    if offset > 0 and st.button("← Newer", use_container_width=True):
        st.session_state["gallery_offset"] = max(0, offset - PAGE_SIZE)
        st.rerun()
with nav2:
    page_no = (offset // PAGE_SIZE) + 1
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    st.markdown(f"<div style='text-align:center'>Page {page_no} / {pages}</div>", unsafe_allow_html=True)
with nav3:
    if offset + PAGE_SIZE < total and st.button("Older →", use_container_width=True):
        st.session_state["gallery_offset"] = offset + PAGE_SIZE
        st.rerun()
