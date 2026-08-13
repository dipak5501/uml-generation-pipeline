import time

import streamlit as st

from ui.api_client import api_get_bytes, api_post
from ui.jobs import (
    active_job_id,
    clear_job,
    fetch_job,
    load_job_results_into_session,
    render_active_job_banner,
    track_job,
)
from ui.theme import apply_theme, hero, panel

st.set_page_config(page_title="UML-Pipeline · Generate", layout="wide", page_icon="▦")
apply_theme(show_job_banner=False)

hero(
    "Generate from text or source code",
    "Paste a requirement paragraph or software source. UML-Pipeline builds a "
    "technical specification, PlantUML, render gate, and multimodal validation scores.",
    chips=["Requirements", "Source code", "Verification"],
)

REQ_EXAMPLES = {
    "(type your own)": "",
    "Bookstore checkout": (
        "As a shopper, I want to add books to a cart and checkout with saved payment methods."
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

panel(
    "Input",
    "Choose Requirement text or Source code, then generate. Pipeline: CoT PlantUML → "
    "validation → render gate → 3 VLMs → weighted composite S + majority vote A (τ=4) → "
    "dataset gate (A=1 and S≥3). The four paper UML types: class, object, component, package. "
    "Generation runs in the background — you can switch pages while it works.",
)

input_mode_label = st.radio(
    "Input type",
    ["Requirement / paragraph", "Software source code"],
    horizontal=True,
)
input_mode = "source_code" if input_mode_label.startswith("Software") else "requirement"

# Example selection must happen before text widgets are created
if "pending_example" in st.session_state:
    st.session_state["free_requirement_input"] = st.session_state.pop("pending_example")
if "free_requirement_input" not in st.session_state:
    st.session_state["free_requirement_input"] = ""

if input_mode == "requirement":
    example_choice = st.selectbox("Optional requirement example", list(REQ_EXAMPLES.keys()))
    if example_choice != "(type your own)":
        if st.session_state.get("_last_example_choice") != example_choice:
            st.session_state["_last_example_choice"] = example_choice
            st.session_state["pending_example"] = REQ_EXAMPLES[example_choice]
            st.rerun()
    else:
        st.session_state["_last_example_choice"] = example_choice
else:
    if st.button("Load sample checkout code"):
        st.session_state["pending_example"] = CODE_EXAMPLE
        st.rerun()

requirement = st.text_area(
    "Your requirement or source code",
    height=260,
    placeholder=(
        "Requirement mode: describe a feature in plain English…\n\n"
        "Code mode: paste Python/Java/JS classes and functions…"
    ),
    label_visibility="collapsed",
    key="free_requirement_input",
)
st.caption(
    "Tips for reliable runs: use 2–8 clear sentences (or a focused class file), pick one "
    "diagram type that matches the content, and avoid pasting entire repos. Long inputs are "
    "auto-clipped for the model but still grounded structurally. Full VLM scoring can take "
    "1–4 minutes; set `VLM_FAST_MODE=true` in `.env` for quicker demos."
)

left, right = st.columns([1.2, 1])
with left:
    diagram_type = st.selectbox(
        "Diagram type",
        ["class", "object", "component", "package"],
    )
with right:
    gen_all = st.checkbox("Also generate the other diagram types", value=False)

can_run = bool((requirement or "").strip())
busy = active_job_id() is not None and (fetch_job(active_job_id() or 0) or {}).get("status") in (
    "pending",
    "running",
    None,
)
run = st.button(
    "Generate + validate",
    type="primary",
    disabled=not can_run or bool(busy),
    use_container_width=True,
)
if not can_run:
    st.caption("Enter a requirement or paste code to enable generation.")
elif busy:
    st.caption("A generation job is already running — wait for it to finish or open another page.")

if run and can_run and not busy:
    text = requirement.strip()
    types = (
        ["class", "object", "component", "package"]
        if gen_all
        else [diagram_type]
    )
    try:
        result = api_post(
            "/api/generate",
            {
                "requirement": text,
                "diagram_type": types[0],
                "diagram_types": types,
                "input_mode": input_mode,
                "async_mode": True,
            },
        )
        job_id = int(result["job_id"])
        track_job(job_id, label="Generate")
        st.success(
            f"Started background job #{job_id} for {len(types)} diagram type(s). "
            "You can switch to Dashboard / Settings — generation will continue."
        )
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

# Poll active job on this page (safe: API work is detached)
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
            st.success(f"Loaded {len(arts)} artifact(s) from job #{job_id}.")
            st.rerun()
    elif job and job.get("status") == "failed":
        clear_job()

artifact = st.session_state.get("last_artifact")
if not artifact:
    st.stop()

st.divider()
st.subheader("Result")
st.markdown("**Your input**")
source_lang = artifact.get("source_language")
artifact_input_mode = artifact.get("input_mode") or input_mode
if artifact_input_mode == "source_code" or source_lang:
    lang = source_lang or "unknown"
    st.caption(f"Input mode: `{artifact_input_mode}` · detected language: `{lang}`")
    st.code(
        artifact["source_requirement"],
        language=lang if lang != "unknown" else None,
    )
else:
    st.caption(f"Input mode: `{artifact_input_mode}`")
    st.write(artifact["source_requirement"])

st.subheader("Paper validation pipeline")
render_ok = artifact["render_status"] == "success"
syntax_ok = not (artifact.get("validation_messages") or "").strip()
scores = artifact.get("model_scores") or []
available = [s for s in scores if s.get("available", True)]
vlm_ok = bool(available) and render_ok
composite = artifact.get("composite_score", 0)
majority_ok = bool(artifact.get("majority_accepted"))
dataset_ok = bool(artifact.get("dataset_accepted"))
votes = artifact.get("affirmative_votes", 0)
tau = artifact.get("acceptance_tau", 4.0)

v1, v2, v3, v4, v5 = st.columns(5)
v1.metric("1. Spec + CoT", "Pass" if artifact.get("used_cot", True) else "Spec only")
v2.metric("2. PlantUML syntax", "Pass" if syntax_ok else "Flags")
v3.metric("3. Render gate", "Pass" if render_ok else "Fail → score 0")
v4.metric("4. Composite S", f"{composite:.2f}")
v5.metric("5. Majority A", f"{'Yes' if majority_ok else 'No'} ({votes}/3 ≥τ={tau:g})")

st.caption(
    f"Dataset entry accepted: **{'Yes' if dataset_ok else 'No'}** "
    f"(requires majority A=1 and composite S ≥ 3.0)."
)

if artifact.get("validation_messages"):
    st.warning(artifact["validation_messages"])

c1, c2 = st.columns([1.1, 0.9])
with c1:
    st.markdown("**Technical specification**")
    if source_lang:
        st.caption(f"Source-code mode · detected language: `{source_lang}`")
    st.text(artifact["technical_spec"])
    st.markdown("**PlantUML**")
    st.code(artifact["plantuml_code"], language="text")
    st.download_button("Download PlantUML", artifact["plantuml_code"], file_name="diagram.puml")
with c2:
    st.metric("Final weighted score", f"{artifact['composite_score']:.3f}")
    st.caption(
        "Weights (MMMU): Qwen 53.1 · LLaMA-Vision 50.7 · Aya-Vision 39.9 · "
        "render failure forces S=0; majority vote τ=4 (≥2 VLMs)."
    )
    st.markdown(
        f"**Render:** `{artifact['render_status']}` · **Type:** `{artifact['diagram_type']}` · "
        f"**Input:** `{artifact_input_mode}`"
        + (f" · **Lang:** `{source_lang}`" if source_lang else "")
        + f" · **Dataset:** `{'accepted' if dataset_ok else 'rejected'}`"
    )
    if artifact["render_status"] == "success":
        try:
            img = api_get_bytes(f"/api/artifacts/{artifact['id']}/image")
            st.image(
                img,
                caption="Rendered + multimodal-validated diagram",
                use_column_width=True,
            )
            st.download_button(
                "Download image",
                img,
                file_name=f"diagram.{artifact.get('image_format', 'png')}",
            )
        except Exception as exc:
            st.error(f"Image load failed: {exc}")
    else:
        st.error("Render failed — paper rule: composite score = 0. PlantUML still available.")

st.subheader("Per-model VLM scores")
model_scores = artifact.get("model_scores") or []
if model_scores:
    st.dataframe(model_scores, use_container_width=True, hide_index=True)
    for row in model_scores:
        label = f"{row.get('model_name') or row.get('model_key')} · score {row.get('score')}"
        with st.expander(label, expanded=bool(row.get("explanation")) and row.get("available", True)):
            st.write(row.get("explanation") or "(no explanation returned)")
else:
    st.info("No per-model scores yet.")

if artifact.get("repair_attempts"):
    st.subheader("Repair attempts")
    st.table(artifact["repair_attempts"])

extras = st.session_state.get("last_artifacts") or []
if len(extras) > 1:
    st.subheader("Other diagram types")
    st.table(
        [
            {
                "id": a["id"],
                "diagram_type": a["diagram_type"],
                "render_status": a["render_status"],
                "composite_score": a["composite_score"],
            }
            for a in extras
        ]
    )
