"""Browse every previously generated UML diagram."""

from __future__ import annotations

import streamlit as st

from ui.api_client import api_get, api_get_bytes
from ui.theme import apply_theme, hero

st.set_page_config(page_title="UML-Pipeline · Generated Diagrams", layout="wide", page_icon="▦")
apply_theme()

PAGE_SIZE = 12

hero(
    "Generated UML diagrams",
    "Every diagram this application has produced — images, PlantUML, scores, and the original requirement.",
    chips=["History", "Gallery", "All diagram types"],
)


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
    meta[1].metric("Score", f"{float(opened.get('composite_score') or 0):.2f}")
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
                st.image(png, use_container_width=True)
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
                    st.image(png, use_container_width=True)
                else:
                    st.caption("Image missing")
            else:
                st.caption(f"No image ({art.get('render_status')})")
            bits = [
                f"score {float(art.get('composite_score') or 0):.2f}",
                "dataset" if art.get("dataset_accepted") else "held out",
            ]
            if art.get("created_at"):
                bits.append(str(art["created_at"]).replace("T", " ")[:16])
            st.caption(" · ".join(bits))
            if st.button("Open", key=f"open-{art['id']}", use_container_width=True):
                st.session_state["gallery_selected"] = art["id"]
                st.rerun()

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
