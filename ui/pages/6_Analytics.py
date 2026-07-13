import pandas as pd
import streamlit as st

from ui.api_client import API_BASE, api_get

st.set_page_config(page_title="Analytics", layout="wide")
st.title("Analytics")

try:
    summary = api_get("/api/analytics/summary")
    dist = api_get("/api/analytics/distributions")
except Exception as exc:
    st.error(exc)
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Artifacts", summary["total_artifacts"])
c2.metric("Render failures", summary["render_failures"])
c3.metric("Package failures", summary["package_failure_count"])
c4.metric(
    "Human↔AI corr",
    f"{summary['human_vs_ai_correlation']:.3f}" if summary.get("human_vs_ai_correlation") is not None else "n/a",
)

st.subheader("Composite score distribution")
comp = dist.get("composite") or {}
st.bar_chart(pd.DataFrame({"score": list(comp.keys()), "count": list(comp.values())}).set_index("score"))

st.subheader("By diagram type")
by = dist.get("by_diagram_type") or {}
for dtype, hist in by.items():
    st.markdown(f"**{dtype}**")
    st.bar_chart(pd.DataFrame({"score": list(hist.keys()), "count": list(hist.values())}).set_index("score"))

st.subheader("Repair stats")
st.write(
    {
        "repair_attempts": summary["repair_attempts"],
        "repair_successes": summary["repair_successes"],
        "by_diagram_type": summary["by_diagram_type"],
    }
)

st.subheader("Export")
st.markdown(
    f"- [JSONL]({API_BASE}/api/export/dataset?fmt=jsonl)\n"
    f"- [CSV]({API_BASE}/api/export/dataset?fmt=csv)\n"
    f"- [Parquet]({API_BASE}/api/export/dataset?fmt=parquet)"
)
