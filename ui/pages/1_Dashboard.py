import streamlit as st

from ui.api_client import api_get

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Dashboard")

try:
    summary = api_get("/api/analytics/summary")
    artifacts = api_get("/api/artifacts")
except Exception as exc:
    st.error(f"API error: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total artifacts", summary["total_artifacts"])
c2.metric("Mean composite", f"{(summary.get('mean_composite') or 0):.3f}")
c3.metric("Render failures", summary["render_failures"])
c4.metric("Human reviews", summary["human_review_count"])

st.subheader("Counts by diagram type")
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
    st.info("No artifacts yet. Generate one from the Single Generation page.")

st.subheader("Recent artifacts")
st.dataframe(artifacts[:20] if artifacts else [], use_container_width=True)
