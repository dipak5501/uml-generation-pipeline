import streamlit as st

from ui.api_client import api_get
from ui.theme import apply_theme, hero, stats_row

st.set_page_config(page_title="Dashboard", layout="wide", page_icon="▦")
apply_theme()

hero(
    "Project dashboard",
    "Live counts, score health, and recent artifacts from your generation runs.",
    chips=["Analytics snapshot", "Thesis demo"],
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
    st.dataframe(rows, use_container_width=True)
else:
    st.info("No artifacts yet. Open Generate and paste a requirement.")

st.subheader("Recent artifacts")
st.dataframe(artifacts[:25] if artifacts else [], use_container_width=True)
