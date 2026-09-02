import streamlit as st

from ui.api_client import api_get, api_get_bytes
from ui.nav import go_eval, go_gallery, go_generate
from ui.theme import apply_theme, hero, show_image, stats_row

st.set_page_config(page_title="UML-Pipeline · Dashboard", layout="wide", page_icon="▦")
apply_theme()

hero("Dashboard", "Live counts and latest diagrams.", chips=["UML-Pipeline"])

try:
    summary = api_get("/api/analytics/summary")
    artifacts = api_get("/api/artifacts", limit=12)
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

stats_row(
    [
        ("Artifacts", str(summary["total_artifacts"])),
        ("Mean S", f"{(summary.get('mean_composite') or 0):.2f}"),
        ("Render fails", str(summary["render_failures"])),
        ("Reviews", str(summary["human_review_count"])),
    ]
)

c1, c2 = st.columns(2)
if c1.button("Generate", type="primary", use_container_width=True):
    go_generate()
if c2.button("All diagrams", use_container_width=True):
    go_gallery()

st.subheader("By diagram type")
by = summary.get("by_diagram_type") or {}
if by:
    st.dataframe(
        [
            {
                "type": k,
                "n": v.get("count"),
                "mean S": v.get("mean_score"),
                "fails": v.get("failures"),
                "majority": v.get("majority"),
                "dataset": v.get("dataset"),
            }
            for k, v in by.items()
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No artifacts yet.")

st.subheader("Recent")
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
                st.caption(
                    f"S {float(art.get('composite_score') or 0):.2f} · "
                    f"A {'yes' if art.get('majority_accepted') else 'no'}"
                )
                if art.get("render_status") == "success":
                    try:
                        show_image(api_get_bytes(f"/api/artifacts/{art['id']}/image"))
                    except Exception:
                        st.caption("Image unavailable")
                a1, a2 = st.columns(2)
                if a1.button("Open", key=f"dash-open-{art['id']}", use_container_width=True):
                    go_gallery(art["id"])
                if a2.button("Rate", key=f"dash-rate-{art['id']}", use_container_width=True):
                    go_eval(art["id"])
