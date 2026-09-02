"""Committee defense tour — paper vs this Mac Studio, RQs, demos, snapshot."""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ui.api_client import api_get, api_get_bytes, api_post
from ui.artifact_view import render_artifact_grid, render_artifact_result
from ui.jobs import (
    active_job_id,
    clear_job,
    fetch_job,
    load_job_results_into_session,
    render_active_job_banner,
    track_job,
)
from ui.theme import apply_theme, hero, panel, stats_row

st.set_page_config(page_title="UML-Pipeline · Thesis Defense", layout="wide", page_icon="▦")
apply_theme(show_job_banner=False)

hero(
    "Thesis defense",
    "Five-minute tour of the method on the Math department Mac Studio. "
    "Paper numbers (DeepSeek-32B, n=8,000) stay in the left column. "
    "Live numbers on the right are this server — a 0.5B LoRA stand-in with the same gates.",
    chips=["Mac Studio server", "RQ1 · RQ2 · RQ3", "Do not mix the two columns"],
)

try:
    briefing = api_get("/api/thesis/briefing")
except Exception as exc:
    st.error(exc)
    st.stop()

live = briefing.get("live") or {}
paper = (briefing.get("paper") or {}).get("overall") or {}
stack = briefing.get("live_stack") or {}
human = briefing.get("human_alignment") or {}
formula = briefing.get("formula") or {}
pkg = briefing.get("package_failures") or {}

st.info(stack.get("note") or "")
st.caption(
    f"Host: {stack.get('host')} · Stage 2 on this machine: {stack.get('stage2')}. "
    f"Paper Stage 2: {paper.get('stage2_model')}."
)

stats_row(
    [
        ("Live artifacts", str(live.get("n") or 0)),
        ("Live mean S", f"{live['mean_s']:.2f}" if live.get("mean_s") is not None else "n/a"),
        ("Live majority A", f"{live['majority_accept_pct']:.1f}%" if live.get("majority_accept_pct") is not None else "n/a"),
        ("Paper mean S", f"{paper.get('mean_s', '—')} (n={paper.get('n', '—')})"),
    ]
)

st.subheader("Formula (same on paper and this server)")
c1, c2, c3 = st.columns(3)
with c1:
    panel("Composite S", formula.get("S") or "")
with c2:
    panel("Majority A", formula.get("A") or "")
with c3:
    panel("Dataset gate", formula.get("dataset") or "")

st.subheader("Paper vs this Mac Studio")
rows = []
paper_types = (briefing.get("paper") or {}).get("by_diagram_type") or {}
live_types = live.get("by_diagram_type") or {}
for dtype in ("class", "object", "component", "package"):
    p = paper_types.get(dtype) or {}
    lv = live_types.get(dtype) or {}
    rows.append(
        {
            "type": dtype,
            "paper render %": p.get("success_pct"),
            "live render %": None if lv.get("success_pct") is None else round(lv["success_pct"], 1),
            "paper mean S": p.get("mean_s"),
            "live mean S": None if lv.get("mean_s") is None else round(lv["mean_s"], 2),
            "paper r (human)": p.get("pearson_r"),
            "live n": lv.get("n"),
        }
    )
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.caption(
    "Paper human r and κ used 40 diagrams and 80 raters on the DeepSeek-32B run. "
    "Live human correlation is empty until reviews are saved on this server (Human Evaluation, 0–6)."
)

st.subheader("Research questions")
for rq in briefing.get("research_questions") or []:
    with st.container(border=True):
        st.markdown(f"**{rq.get('id')}.** {rq.get('text')}")
        st.caption(rq.get("where"))

h1, h2, h3, h4 = st.columns(4)
h1.metric("Live reviews", str(human.get("n_reviews") or 0))
h2.metric("Pearson r", f"{human['pearson_r']:.3f}" if human.get("pearson_r") is not None else "n/a")
h3.metric("Spearman ρ", f"{human['spearman_rho']:.3f}" if human.get("spearman_rho") is not None else "n/a")
h4.metric("Raters", str(human.get("n_raters") or 0))
st.caption(human.get("note") or "")

st.subheader("Run a demo on this Mac")
st.caption("Jobs run on the Mac Studio. Score with VLMs unless you need a fast diagram-only pass.")
score_vlm = st.checkbox("Score with the three VLMs (paper S and A)", value=True, key="defense_vlm")
demos = briefing.get("demo_cases") or []
cols = st.columns(len(demos) or 1)
for col, demo in zip(cols, demos):
    with col:
        with st.container(border=True):
            st.markdown(f"**{demo.get('rq')} · {demo.get('title')}**")
            st.caption(demo.get("why"))
            if st.button(f"Run {demo.get('id')}", key=f"run-{demo.get('id')}", use_container_width=True):
                try:
                    result = api_post(
                        "/api/generate",
                        {
                            "requirement": demo["requirement"],
                            "diagram_type": demo.get("diagram_type") or "class",
                            "diagram_types": demo.get("diagram_types") or [demo.get("diagram_type") or "class"],
                            "input_mode": demo.get("input_mode") or "requirement",
                            "async_mode": True,
                            "skip_vlm": not score_vlm,
                        },
                    )
                    track_job(int(result["job_id"]), label=demo.get("title") or "Defense demo")
                    st.success(f"Queued job #{result['job_id']} on the Mac Studio.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

job_id = active_job_id()
if job_id is not None:
    job = render_active_job_banner(auto_refresh=False)
    if job and job.get("status") in ("pending", "running"):
        st.progress(min(0.99, (job.get("completed") or 0) / max(job.get("total") or 1, 1)))
        time.sleep(2.0)
        st.rerun()
    elif job and job.get("status") == "completed":
        arts = load_job_results_into_session(job_id)
        clear_job()
        if arts:
            st.rerun()
    elif job and job.get("status") == "failed":
        st.error(job.get("error") or "Demo failed")
        if st.button("Dismiss failed job"):
            clear_job()
            st.rerun()

arts = st.session_state.get("last_artifacts") or []
if st.session_state.get("last_artifact") and not arts:
    arts = [st.session_state["last_artifact"]]
if arts:
    st.subheader("Latest run")
    render_artifact_result(arts[0], key_prefix="def")
    if len(arts) > 1:
        render_artifact_grid(arts, key_prefix="def-grid")

st.subheader("RQ3 · Package failures on this server")
st.caption(
    f"Package artifacts: {pkg.get('package_total', 0)} · failures: {pkg.get('package_failures', 0)} · "
    f"rate: {pkg.get('failure_rate')}"
)
if pkg.get("by_category"):
    st.bar_chart(pd.DataFrame({"count": pkg["by_category"]}).rename_axis("category"))
examples = pkg.get("examples") or {}
if examples:
    for cat, rows_ex in examples.items():
        with st.expander(f"{cat} ({len(rows_ex)} example(s))"):
            for row in rows_ex:
                st.markdown(f"Artifact #{row.get('id')} · S={row.get('composite_score')}")
                st.code(row.get("plantuml_preview") or "", language="text")
else:
    st.write("No failed package diagrams stored yet. Run the package demo to populate this gallery.")

st.subheader("Take-home snapshot")
st.caption("Seed 42, up to 10 artifacts per type from this Mac Studio database — not the paper 8k set.")
s1, s2 = st.columns(2)
with s1:
    try:
        snap_json = api_get_bytes("/api/thesis/snapshot?fmt=json&seed=42&n_per_type=10")
        st.download_button("Download JSON snapshot", snap_json, file_name="uml_eval_snapshot.json")
    except Exception as exc:
        st.caption(f"JSON snapshot: {exc}")
with s2:
    try:
        snap_csv = api_get_bytes("/api/thesis/snapshot?fmt=csv&seed=42&n_per_type=10")
        st.download_button("Download CSV snapshot", snap_csv, file_name="uml_eval_snapshot.csv")
    except Exception as exc:
        st.caption(f"CSV snapshot: {exc}")
