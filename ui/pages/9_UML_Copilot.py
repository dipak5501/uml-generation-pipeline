"""UML Copilot — chat → generate / correct PlantUML on the Mac Studio pipeline."""

from __future__ import annotations

import time

import streamlit as st

from ui.api_client import api_get, api_post
from ui.artifact_view import render_artifact_result
from ui.jobs import (
    active_job_id,
    clear_job,
    load_job_results_into_session,
    render_active_job_banner,
    track_job,
)
from ui.theme import apply_theme, hero

st.set_page_config(page_title="UML-Pipeline · Copilot", layout="wide", page_icon="◈")
apply_theme(show_job_banner=False)

hero(
    "UML Copilot",
    "Mini ChatGPT for UML — clarify in chat, then generate or correct via the PlantUML pipeline.",
    chips=["chat", "generate", "correct"],
)

if "copilot_messages" not in st.session_state:
    st.session_state["copilot_messages"] = [
        {
            "role": "assistant",
            "content": (
                "Hi — I’m your UML Copilot. Tell me what system you’re designing "
                "(even roughly), and I’ll ask a few clarifying questions like ChatGPT "
                "before we generate a diagram.\n\n"
                "Examples:\n"
                "- “Campus parking permits and citations”\n"
                "- “What should go in a component diagram for a payments API?”\n"
                "- After a diagram exists: “Add a Payment class linked to Order”\n\n"
                "When you’re ready, say **generate** or use the Generate button."
            ),
        }
    ]
if "copilot_artifact_id" not in st.session_state:
    st.session_state["copilot_artifact_id"] = None

with st.sidebar:
    st.markdown("### Copilot")
    diagram_type = st.selectbox("Diagram type", ["class", "object", "component", "package"])
    skip_vlm = st.checkbox("Skip VLM scoring (faster)", value=True)
    try:
        health = api_get("/api/copilot/health")
    except Exception as exc:
        health = None
        st.warning(f"Copilot health unavailable: {exc}")
    if health:
        st.caption(
            f"Chat: `{health.get('copilot_model')}` · "
            f"{'ready' if health.get('model_present') else 'model missing'}"
        )
        st.caption(f"Generate: {health.get('generation_provider') or '—'}")
        if health.get("status") != "ok":
            st.info(health.get("message") or "Ollama degraded")
    if st.button("Clear chat", use_container_width=True):
        st.session_state["copilot_messages"] = []
        st.session_state["copilot_artifact_id"] = None
        clear_job()
        st.rerun()

for msg in st.session_state["copilot_messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

cols = st.columns(3)
force_generate = cols[0].button("Generate from last message", use_container_width=True)
force_correct = cols[1].button(
    "Apply correction to last diagram",
    use_container_width=True,
    disabled=st.session_state.get("copilot_artifact_id") is None,
)
force_chat = cols[2].button("Chat only (no pipeline)", use_container_width=True)

prompt = st.chat_input("Ask, describe a system, or request a correction…")


def _history_payload() -> list[dict[str, str]]:
    """Send recent turns so the model can continue a clarifying dialogue."""
    out: list[dict[str, str]] = []
    for m in st.session_state["copilot_messages"][-16:]:
        role = m.get("role") or "user"
        content = (m.get("content") or "").strip()
        # Cap each turn so huge PlantUML paste-backs don't blow the context.
        if len(content) > 2000:
            content = content[:2000] + "…"
        if content:
            out.append({"role": role, "content": content})
    return out


def _run_turn(message: str, action: str) -> None:
    st.session_state["copilot_messages"].append({"role": "user", "content": message})
    try:
        result = api_post(
            "/api/copilot/turn",
            {
                "message": message,
                "action": action,
                "diagram_type": diagram_type,
                "artifact_id": st.session_state.get("copilot_artifact_id"),
                "history": _history_payload(),
                "skip_vlm": skip_vlm,
                "input_mode": "requirement",
            },
        )
    except Exception as exc:
        st.session_state["copilot_messages"].append(
            {"role": "assistant", "content": f"Error: {exc}"}
        )
        st.rerun()
        return

    reply = result.get("reply") or "(no reply)"
    st.session_state["copilot_messages"].append({"role": "assistant", "content": reply})

    job = result.get("job")
    if job and job.get("id") is not None:
        track_job(int(job["id"]), label="Copilot generate")

    art = result.get("artifact")
    if art and art.get("id") is not None:
        st.session_state["copilot_artifact_id"] = art["id"]
        st.session_state["last_artifact"] = art
    elif result.get("artifact_id") is not None:
        st.session_state["copilot_artifact_id"] = result["artifact_id"]

    st.rerun()


action = "auto"
message = None
if force_generate or force_correct or force_chat:
    last_user = next(
        (
            m["content"]
            for m in reversed(st.session_state["copilot_messages"])
            if m["role"] == "user"
        ),
        "",
    )
    message = prompt or last_user or None
    if not message:
        st.warning("Type a message first.")
    elif force_generate:
        action = "generate"
    elif force_correct:
        action = "correct"
    else:
        action = "chat"
elif prompt:
    message = prompt
    action = "auto"

if message:
    _run_turn(message, action)

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
            st.session_state["copilot_artifact_id"] = arts[0].get("id")
            st.session_state["last_artifact"] = arts[0]
            st.session_state["copilot_messages"].append(
                {
                    "role": "assistant",
                    "content": f"Generation finished — diagram #{arts[0].get('id')}.",
                }
            )
        st.rerun()
    elif job and job.get("status") == "failed":
        st.error(job.get("error") or "Generation failed")
        if st.button("Dismiss failed job"):
            clear_job()
            st.rerun()

aid = st.session_state.get("copilot_artifact_id")
art = st.session_state.get("last_artifact")
if art and art.get("id") == aid:
    st.divider()
    st.subheader(f"Current diagram #{aid}")
    render_artifact_result(art, key_prefix="copilot")
elif aid is not None:
    try:
        detail = api_get(f"/api/artifacts/{aid}")
        st.session_state["last_artifact"] = detail
        st.divider()
        st.subheader(f"Current diagram #{aid}")
        render_artifact_result(detail, key_prefix="copilot")
    except Exception as exc:
        st.caption(f"Could not load artifact #{aid}: {exc}")
