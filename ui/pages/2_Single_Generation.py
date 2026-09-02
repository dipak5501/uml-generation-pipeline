import time

import streamlit as st

from ui.artifact_view import render_artifact_grid, render_artifact_result, vlm_skipped
from ui.jobs import (
    active_job_id,
    clear_job,
    fetch_job,
    load_job_results_into_session,
    render_active_job_banner,
    track_job,
)
from ui.theme import apply_theme, hero
from ui.api_client import api_post

st.set_page_config(page_title="UML-Pipeline · Generate", layout="wide", page_icon="▦")
apply_theme(show_job_banner=False)

hero(
    "Generate",
    "Requirement or source code → PlantUML → render → VLM scores (S, A, dataset gate).",
    chips=["class", "object", "component", "package"],
)

REQ_EXAMPLES = {
    "(type your own)": "",
    "Bookstore checkout": (
        "As a shopper, I want to add books to a cart and checkout with saved payment methods."
    ),
    "Campus parking office": (
        "Campus parking office: students and staff register vehicles, purchase permits, "
        "and receive citations for violations. Officers record citations against a vehicle "
        "and a permit. A payment clerk records payments. The system tracks lots, spaces, "
        "and whether a permit is valid for a given lot."
    ),
    "Hospital appointments": (
        "Patients book appointments with doctors across multiple clinics and receive reminders."
    ),
    "Food delivery flow": (
        "When a customer places a food order, the restaurant confirms, a courier is assigned, "
        "then delivery is completed or cancelled if payment fails."
    ),
}

CODE_EXAMPLE = '''class User:
    def __init__(self, user_id: int, email: str):
        self.user_id = user_id
        self.email = email

    def authenticate(self, password: str) -> bool:
        return bool(password)


class Order:
    def __init__(self, order_id: int, user: User):
        self.order_id = order_id
        self.user = user
        self.items = []

    def add_item(self, item: "OrderItem") -> None:
        self.items.append(item)


class OrderItem:
    def __init__(self, sku: str, price: float):
        self.sku = sku
        self.price = price


class PaymentService:
    def charge(self, order: Order, amount: float) -> bool:
        return amount > 0
'''

input_mode_label = st.radio(
    "Input type",
    ["Requirement / paragraph", "Software source code"],
    horizontal=True,
)
input_mode = "source_code" if input_mode_label.startswith("Software") else "requirement"

if "pending_example" in st.session_state:
    st.session_state["free_requirement_input"] = st.session_state.pop("pending_example")
if "free_requirement_input" not in st.session_state:
    st.session_state["free_requirement_input"] = ""

if input_mode == "requirement":
    example_choice = st.selectbox("Example", list(REQ_EXAMPLES.keys()))
    if example_choice != "(type your own)":
        if st.session_state.get("_last_example_choice") != example_choice:
            st.session_state["_last_example_choice"] = example_choice
            st.session_state["pending_example"] = REQ_EXAMPLES[example_choice]
            st.rerun()
    else:
        st.session_state["_last_example_choice"] = example_choice
elif st.button("Load sample checkout code"):
    st.session_state["pending_example"] = CODE_EXAMPLE
    st.rerun()

requirement = st.text_area(
    "Requirement or source code",
    height=220,
    placeholder="Describe a feature, or paste Python / Java / C…",
    label_visibility="collapsed",
    key="free_requirement_input",
)

left, right = st.columns([1.2, 1])
with left:
    diagram_type = st.selectbox("Diagram type", ["class", "object", "component", "package"])
with right:
    gen_all = st.checkbox("Also generate the other three types", value=False)
    score_vlm = st.checkbox("Score with VLMs", value=True)
    skip_repair = False
    skip_majority = False
    with st.expander("Advanced"):
        skip_repair = st.checkbox("Skip repair loop", value=False)
        skip_majority = st.checkbox("Skip majority gate for dataset entry", value=False)

can_run = bool((requirement or "").strip())
jid = active_job_id()
job_now = fetch_job(jid) if jid is not None else None
busy = bool(job_now and job_now.get("status") in ("pending", "running"))

run = st.button(
    "Generate",
    type="primary",
    disabled=not can_run or busy,
    use_container_width=True,
)
if not can_run:
    st.caption("Enter a requirement or paste code.")
elif busy:
    st.caption("A job is already running.")

if run and can_run and not busy:
    types = ["class", "object", "component", "package"] if gen_all else [diagram_type]
    try:
        result = api_post(
            "/api/generate",
            {
                "requirement": requirement.strip(),
                "diagram_type": types[0],
                "diagram_types": types,
                "input_mode": input_mode,
                "async_mode": True,
                "skip_vlm": not score_vlm,
                "skip_repair": skip_repair,
                "skip_majority": skip_majority,
            },
        )
        track_job(int(result["job_id"]), label="Generate")
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
        st.error(job.get("error") or "Generation failed")
        if st.button("Dismiss failed job"):
            clear_job()
            st.rerun()

artifact = st.session_state.get("last_artifact")
if not artifact:
    st.stop()

st.divider()
st.subheader("Result")
render_artifact_result(artifact, key_prefix="gen")

extras = st.session_state.get("last_artifacts") or []
if len(extras) > 1:
    st.subheader("All types from this run")
    render_artifact_grid(extras, key_prefix="gen-grid")
    if (
        artifact.get("input_mode") == "source_code"
        and artifact.get("render_status") == "success"
        and not vlm_skipped(artifact)
        and float(artifact.get("composite_score") or 0) < 3.0
    ):
        st.caption("S < 3: a richer snippet (several types and relationships) usually scores higher.")
