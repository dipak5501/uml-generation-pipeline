"""UML Copilot — chat + generate + correct on top of existing orchestration."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any, Literal

import httpx
from sqlmodel import Session

from app.models import RepairAttempt, RenderAttempt, UMLArtifact
from app.providers.factory import OllamaProvider, build_chat_provider
from app.providers.mock_provider import MockProvider
from app.services.artifacts import artifact_detail
from app.services.orchestration import apply_verification, score_image
from app.services.plantuml_validate import (
    ensure_plantuml_bounds,
    sanitize_plantuml_output,
    validate_diagram,
)
from app.services.acceptance import FAILURE_SEMANTIC
from app.services.repair import repair_plantuml
from app.services.scoring import verify_scores
from app.settings import Settings, get_settings
from uml_pipeline.render import extract_plantuml_block, render_plantuml

logger = logging.getLogger(__name__)

Intent = Literal["generate", "correct", "chat"]

_GENERATE_HINTS = re.compile(
    r"\b(generate|create|draw|make|build)\b.*\b(diagram|uml|plantuml)\b|"
    r"\b(class|component|package|object)\s+diagram\b|"
    r"\b(uml|plantuml)\b",
    re.I,
)
_CORRECT_HINTS = re.compile(
    r"\b(fix|correct|repair|change|update|add|remove|rename|edit|adjust|"
    r"modify|instead|should|missing|wrong)\b",
    re.I,
)
_QUESTION_HINTS = re.compile(
    r"^\s*(what|why|how|who|when|where|which|can you|do you|could you|"
    r"should we|help me|explain)\b|\?\s*$",
    re.I,
)
# Explicit "go generate now" — avoids jumping to the pipeline on vague descriptions.
_GO_GENERATE = re.compile(
    r"\b(generate|create|draw|make|build)\b.{"
    r"0,40}\b(diagram|uml|plantuml|class|component|package|object)\b|"
    r"\b(please\s+)?(generate|create|draw)\b|"
    r"\bgo\s+ahead\b|\bready\s+to\s+(generate|create)\b",
    re.I,
)


def detect_intent(message: str, *, has_artifact: bool) -> Intent:
    """Prefer chat for clarifying dialogue; only auto-generate on clear intent."""
    text = (message or "").strip()
    if not text:
        return "chat"
    if _QUESTION_HINTS.search(text) and not _GO_GENERATE.search(text):
        return "chat"
    if has_artifact and _CORRECT_HINTS.search(text):
        return "correct"
    # ChatGPT-style: vague system descriptions stay in chat so we can ask
    # clarifying questions. Explicit generate language (or the Generate button)
    # starts the PlantUML pipeline.
    if _GO_GENERATE.search(text) or (
        _GENERATE_HINTS.search(text) and len(text) >= 24
    ):
        return "generate"
    if has_artifact and len(text) >= 12 and not text.endswith("?"):
        return "correct"
    return "chat"


_CHAT_SYSTEM = (
    "You are UML Copilot — a helpful, conversational assistant like a mini ChatGPT "
    "for designing UML diagrams (class, object, component, package) on a local "
    "PlantUML pipeline.\n\n"
    "How to talk:\n"
    "- Be warm, clear, and concise (usually 2–6 short sentences or a short bullet list).\n"
    "- Ask clarifying questions when the request is vague: domain, key entities, "
    "relationships, diagram type, scope, or constraints. Ask 1–3 focused questions "
    "at a time — do not dump a long questionnaire.\n"
    "- Remember the conversation: build on earlier answers; do not re-ask what "
    "they already told you.\n"
    "- When you have enough detail, summarize the planned diagram in plain "
    "language and invite them to say “generate” (or use Generate) to run the "
    "pipeline — or offer to apply a correction to the current diagram.\n"
    "- Explain UML concepts briefly when asked.\n"
    "- Do not invent long PlantUML source unless they explicitly ask to see code; "
    "generation and repair run through the pipeline, not this chat.\n"
    "- Never claim you already rendered a diagram unless the pipeline context says so."
)


def resolve_intent(
    message: str,
    action: str,
    *,
    has_artifact: bool,
) -> Intent:
    act = (action or "auto").strip().lower()
    if act in {"generate", "correct", "chat"}:
        if act == "correct" and not has_artifact:
            return "generate" if len((message or "").strip()) >= 12 else "chat"
        return act  # type: ignore[return-value]
    return detect_intent(message, has_artifact=has_artifact)


def build_copilot_chat_provider(settings: Settings | None = None):
    """Always prefer local Ollama for dialogue (independent of USE_OLLAMA)."""
    settings = settings or get_settings()
    model = (settings.copilot_model or "llama3.2:1b").strip() or "llama3.2:1b"
    # Chat stays on primary Ollama (:11434) so the Qwen VLM host (:11435) stays free.
    if settings.mock_providers:
        return MockProvider()
    try:
        return OllamaProvider(model, ollama_url=settings.ollama_base_url.rstrip("/"))
    except Exception:
        logger.warning("Ollama copilot provider failed; falling back to chat provider")
        return build_chat_provider(settings, model=settings.spec_model)


def ollama_copilot_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    base = settings.ollama_base_url.rstrip("/")
    model = (settings.copilot_model or "llama3.2:1b").strip()
    out: dict[str, Any] = {
        "ollama_base_url": base,
        "copilot_model": model,
        "reachable": False,
        "model_present": False,
        "models": [],
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{base}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in (r.json().get("models") or [])]
        out["reachable"] = True
        out["models"] = names
        out["model_present"] = any(
            n == model or n.startswith(f"{model}:") or n.split(":")[0] == model.split(":")[0]
            for n in names
        )
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def chat_reply(
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    artifact_summary: str = "",
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    provider = build_copilot_chat_provider(settings)
    parts: list[str] = []
    if artifact_summary:
        parts.append(f"[Current diagram context]\n{artifact_summary}\n")
    # Multi-turn memory: keep a longer window so clarifying Q&A sticks.
    prior_turns = (history or [])[-12:]
    if prior_turns:
        parts.append("[Conversation so far]")
        for turn in prior_turns:
            role = (turn.get("role") or "user").strip().lower()
            label = "Assistant" if role == "assistant" else "User"
            content = (turn.get("content") or "").strip()
            if content:
                parts.append(f"{label}: {content}")
        parts.append("")
    parts.append(f"User: {message.strip()}")
    parts.append(
        "Assistant: (reply helpfully; ask clarifying questions if needed; "
        "do not dump PlantUML unless asked)"
    )
    user = "\n".join(parts)
    try:
        return (provider.chat(_CHAT_SYSTEM, user, temperature=0.55) or "").strip()
    except Exception as exc:
        logger.warning("Copilot chat failed: %s", exc)
        return (
            "I could not reach the local chat model. "
            "You can still use Generate or Apply correction — those use the PlantUML pipeline."
        )


def _artifact_brief(detail: dict[str, Any] | None) -> str:
    if not detail:
        return ""
    code = (detail.get("plantuml_code") or "")[:1200]
    return (
        f"id=#{detail.get('id')} type={detail.get('diagram_type')} "
        f"render={detail.get('render_status')}\nPlantUML excerpt:\n{code}"
    )


def apply_user_correction(
    session: Session,
    artifact_id: int,
    correction: str,
    *,
    settings: Settings | None = None,
    skip_vlm: bool = True,
) -> dict[str, Any]:
    """Edit the last diagram from a natural-language correction, then re-render."""
    settings = settings or get_settings()
    a = session.get(UMLArtifact, artifact_id)
    if not a:
        raise ValueError(f"Artifact {artifact_id} not found")

    correction = (correction or "").strip()
    if len(correction) < 3:
        raise ValueError("Correction text is too short")

    # Prefer an explicit LLM edit of the PlantUML; fall back to repair strategies.
    provider = build_copilot_chat_provider(settings)
    system = (
        f"You output only valid PlantUML for a {a.diagram_type} diagram. "
        "Apply the user's correction. Keep entities that still make sense. "
        "Do not change diagram type. No markdown fences."
    )
    prompt = (
        f"Technical specification:\n{(a.technical_spec or '')[:4000]}\n\n"
        f"Current PlantUML:\n{a.plantuml_code}\n\n"
        f"User correction:\n{correction}\n"
    )
    try:
        raw = provider.chat(system, prompt, temperature=0.15)
        edited = sanitize_plantuml_output(
            ensure_plantuml_bounds(extract_plantuml_block(raw)),
            diagram_type=a.diagram_type,
        )
    except Exception as exc:
        logger.warning("Direct correction chat failed (%s); using repair_plantuml", exc)
        result = repair_plantuml(
            a.plantuml_code,
            a.technical_spec or "",
            a.diagram_type,
            [f"user correction: {correction}"],
            repair_notes=correction,
            settings=settings,
            category=FAILURE_SEMANTIC,
        )
        edited = result.code

    validation = validate_diagram(edited, a.diagram_type)
    if not validation.ok:
        # One repair pass with the user note if the edit is invalid.
        repaired = repair_plantuml(
            edited,
            a.technical_spec or "",
            a.diagram_type,
            list(validation.messages),
            repair_notes=correction,
            settings=settings,
        )
        edited = repaired.code
        validation = validate_diagram(edited, a.diagram_type)

    session.add(
        RepairAttempt(
            artifact_id=a.id,
            attempt_number=1,
            before_code=a.plantuml_code,
            after_code=edited,
            reason=f"copilot correction: {correction[:240]}",
            success=validation.ok,
        )
    )
    a.plantuml_code = edited
    a.validation_messages = "; ".join(validation.messages)[:2000] if validation.messages else None

    out_dir = settings.artifact_dir / str(a.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    img, err = render_plantuml(
        a.plantuml_code, out_dir, settings.plantuml_jar, fmt=settings.image_format
    )
    session.add(
        RenderAttempt(
            artifact_id=a.id,
            attempt_number=1,
            success=img is not None,
            error_output=err,
            image_path=str(img) if img else None,
            fmt=settings.image_format,
        )
    )
    if img:
        stable = out_dir / f"diagram.{settings.image_format}"
        if Path(img) != stable:
            shutil.copy2(img, stable)
        a.image_path = str(stable)
        a.render_status = "success"
        if skip_vlm:
            a.composite_score = a.composite_score or 0.0
            note = "VLM ensemble skipped (copilot correction)"
            msgs = a.validation_messages or ""
            if note not in msgs:
                a.validation_messages = f"{msgs}; {note}".strip("; ")
        else:
            scores, meta, _ = score_image(stable, a.technical_spec or "", settings)
            verification = verify_scores(
                scores,
                settings.vlm_weight_map,
                render_ok=True,
                tau=settings.acceptance_tau,
                min_composite=settings.min_composite_for_dataset,
            )
            apply_verification(a, scores, meta, verification, session, clear_existing=True)
    else:
        a.render_status = "failed"
        a.composite_score = 0.0
        a.majority_accepted = False
        a.affirmative_votes = 0
        a.dataset_accepted = False

    session.add(a)
    session.commit()
    detail = artifact_detail(session, a.id)
    assert detail
    return detail


def run_copilot_turn(
    session: Session,
    *,
    message: str,
    action: str = "auto",
    diagram_type: str = "class",
    artifact_id: int | None = None,
    history: list[dict[str, str]] | None = None,
    skip_vlm: bool = True,
    input_mode: str = "requirement",
    project_id: int | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Handle one copilot turn: chat, async generate, or in-place correction."""
    from app.jobs.runner import enqueue_generation
    from app.models import GenerationJob
    from app.services.orchestration import get_or_create_default_project

    settings = settings or get_settings()
    message = (message or "").strip()
    if len(message) < 1:
        raise ValueError("message is required")

    has_artifact = artifact_id is not None
    intent = resolve_intent(message, action, has_artifact=has_artifact)

    prior_detail = None
    if artifact_id is not None:
        prior_detail = artifact_detail(session, artifact_id)

    reply = ""
    job_payload = None
    artifact = None

    if intent == "generate":
        project = get_or_create_default_project(session)
        pid = project_id or project.id
        job_id = enqueue_generation(
            session,
            message,
            [diagram_type],
            input_mode=input_mode,
            project_id=pid,
            mode="single",
            skip_vlm=skip_vlm,
            skip_repair=False,
            skip_majority=False,
        )
        job = session.get(GenerationJob, job_id)
        assert job is not None
        job_payload = {
            "id": job.id,
            "status": job.status,
            "mode": job.mode,
            "total": job.total,
            "completed": job.completed,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        reply = (
            f"Generating a **{diagram_type}** diagram from your message "
            f"(job #{job.id}). PlantUML uses the local LoRA when enabled; "
            "I'll show the result when the job finishes."
        )
        # Optional short chat ack (best-effort; never block generate).
        try:
            ack = chat_reply(
                f"Acknowledge briefly that you are generating a {diagram_type} "
                f"diagram for: {message[:400]}",
                history=history,
                settings=settings,
            )
            if ack and len(ack) < 400:
                reply = ack
        except Exception:
            pass

    elif intent == "correct":
        if artifact_id is None:
            raise ValueError("correct requires artifact_id")
        artifact = apply_user_correction(
            session,
            artifact_id,
            message,
            settings=settings,
            skip_vlm=skip_vlm,
        )
        ok = artifact.get("render_status") == "success"
        reply = (
            f"Applied your correction to diagram #{artifact_id}. "
            + ("Render succeeded." if ok else "Render failed — check PlantUML.")
        )
        try:
            ack = chat_reply(
                f"Briefly confirm you applied this correction: {message[:300]}",
                history=history,
                artifact_summary=_artifact_brief(artifact),
                settings=settings,
            )
            if ack and len(ack) < 500:
                reply = ack
        except Exception:
            pass

    else:
        reply = chat_reply(
            message,
            history=history,
            artifact_summary=_artifact_brief(prior_detail),
            settings=settings,
        )

    return {
        "intent": intent,
        "reply": reply,
        "job": job_payload,
        "artifact": artifact,
        "artifact_id": (artifact or {}).get("id") if artifact else artifact_id,
        "copilot_model": settings.copilot_model,
        "diagram_type": diagram_type,
    }
