import pandas as pd
import streamlit as st

from ui.theme import apply_theme

from ui.api_client import API_BASE, api_get, api_get_bytes

st.set_page_config(page_title="UML-Pipeline · Analytics", layout="wide")
apply_theme()
st.title("Analytics")

try:
    summary = api_get("/api/analytics/summary")
    dist = api_get("/api/analytics/distributions")
except Exception as exc:
    st.error(exc)
    st.stop()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Artifacts", summary["total_artifacts"])
c2.metric("Render failures", summary["render_failures"])
c3.metric("Package failures", summary["package_failure_count"])
c4.metric("Majority accepted", summary.get("majority_accepted_count", 0))
c5.metric("Dataset accepted", summary.get("dataset_accepted_count", 0))
c6.metric(
    "Human↔AI corr",
    f"{summary['human_vs_ai_correlation']:.3f}" if summary.get("human_vs_ai_correlation") is not None else "n/a",
)
if summary.get("majority_acceptance_rate") is not None:
    st.caption(
        f"Majority acceptance {100 * summary['majority_acceptance_rate']:.1f}% · "
        f"human reviews {summary.get('human_review_count', 0)} · "
        f"pairs {summary.get('human_vs_ai_n', 0)}"
        + (
            f" · Spearman {summary['human_vs_ai_spearman']:.3f}"
            if summary.get("human_vs_ai_spearman") is not None
            else ""
        )
    )

st.subheader("Composite score distribution")
comp = dist.get("composite") or {}
st.bar_chart(pd.DataFrame({"score": list(comp.keys()), "count": list(comp.values())}).set_index("score"))

st.subheader("By diagram type")
by = dist.get("by_diagram_type") or {}
for dtype, hist in by.items():
    st.markdown(f"**{dtype}**")
    st.bar_chart(pd.DataFrame({"score": list(hist.keys()), "count": list(hist.values())}).set_index("score"))

try:
    adapt = api_get("/api/adaptation/status")
except Exception:
    adapt = None
if adapt and (adapt.get("generators") or adapt.get("recent")):
    st.subheader("Self-adaptation")
    st.caption("Win rates the pipeline uses to pick the next generator and repair strategy.")
    gens = adapt.get("generators") or {}
    if gens:
        rows = [
            {"type": dt, "generator": name, **cell}
            for dt, cells in gens.items()
            for name, cell in cells.items()
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("Package failures")
try:
    pkg = api_get("/api/analytics/package-failures")
except Exception:
    pkg = None
if pkg:
    st.caption(f"{pkg.get('package_failures', 0)} failed / {pkg.get('package_total', 0)} package artifacts")
    if pkg.get("by_category"):
        st.bar_chart(pd.DataFrame({"count": pkg["by_category"]}).rename_axis("category"))
    for cat, rows_ex in (pkg.get("examples") or {}).items():
        with st.expander(f"{cat}"):
            for row in rows_ex:
                st.markdown(f"#{row.get('id')} · S={row.get('composite_score')}")
                st.code(row.get("plantuml_preview") or "", language="text")

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
try:
    snap = api_get_bytes("/api/thesis/snapshot?fmt=csv&seed=42&n_per_type=10")
    st.download_button("Download 40-artifact snapshot (CSV)", snap, file_name="uml_eval_snapshot.csv")
except Exception:
    pass
