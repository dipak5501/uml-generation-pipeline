import streamlit as st

from ui.api_client import api_get, api_get_bytes
from ui.theme import apply_theme, hero, stats_row

st.set_page_config(page_title="UML-Pipeline · Dashboard", layout="wide", page_icon="▦")
apply_theme()

hero(
    "Dashboard",
    "Live counts, score health, and recent artifacts from generation runs.",
    chips=["UML-Pipeline", "Analytics"],
)

try:
    summary = api_get("/api/analytics/summary")
    artifacts = api_get("/api/artifacts")
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

stats_row(
    [
        ("Artifacts", str(summary["total_artifacts"])),
        ("Mean score", f"{(summary.get('mean_composite') or 0):.2f}"),
        ("Render fails", str(summary["render_failures"])),
        ("Human reviews", str(summary["human_review_count"])),
    ]
)

st.subheader("By diagram type")
by = summary.get("by_diagram_type") or {}
if by:
    rows = [
        {
            "diagram_type": k,
            "count": v.get("count"),
            "mean_score": v.get("mean_score"),
            "failures": v.get("failures"),
        }
        for k, v in by.items()
    ]
    st.table(rows)
else:
    st.info("No artifacts yet. Open Generate and paste a requirement.")

st.subheader("Recent generated diagrams")
st.caption("Open **Generated Diagrams** in the sidebar to browse the full history.")
recent = [a for a in (artifacts or []) if a.get("has_image") or a.get("render_status") == "success"][:6]
if not recent and artifacts:
    recent = artifacts[:6]
if not recent:
    st.info("No diagrams stored yet.")
else:
    cols = st.columns(3)
    for i, art in enumerate(recent):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**#{art['id']} · {art['diagram_type']}**")
                st.caption(" ".join((art.get("source_requirement") or "").split())[:100])
                if art.get("render_status") == "success":
                    try:
                        st.image(api_get_bytes(f"/api/artifacts/{art['id']}/image"), use_container_width=True)
                    except Exception:
                        st.caption("Image unavailable")
                else:
                    st.caption(f"Render: {art.get('render_status')}")
