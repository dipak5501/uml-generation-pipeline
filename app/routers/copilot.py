"""UML Copilot API — conversational generate / correct on Mac Studio."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.schemas import (
    CopilotHealthResponse,
    CopilotTurnRequest,
    CopilotTurnResponse,
    JobResponse,
)
from app.security import require_api_access, safe_internal_error
from app.services.copilot import ollama_copilot_status, run_copilot_turn
from app.settings import get_settings

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.get("/health", response_model=CopilotHealthResponse)
def copilot_health():
    settings = get_settings()
    status = ollama_copilot_status(settings)
    ok = bool(status.get("reachable") and status.get("model_present"))
    msg = "ready"
    if not status.get("reachable"):
        msg = "Ollama not reachable on copilot port"
    elif not status.get("model_present"):
        msg = f"Pull model: ollama pull {settings.copilot_model}"
    return CopilotHealthResponse(
        status="ok" if ok else "degraded",
        ollama_base_url=str(status.get("ollama_base_url") or ""),
        copilot_model=str(status.get("copilot_model") or settings.copilot_model),
        reachable=bool(status.get("reachable")),
        model_present=bool(status.get("model_present")),
        models=list(status.get("models") or []),
        generation_provider=settings.provider_summary or settings.provider_name,
        message=msg,
    )


@router.post("/turn", response_model=CopilotTurnResponse)
def copilot_turn(
    req: CopilotTurnRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    settings = get_settings()
    try:
        result = run_copilot_turn(
            session,
            message=req.message,
            action=req.action,
            diagram_type=req.diagram_type,
            artifact_id=req.artifact_id,
            history=req.history,
            skip_vlm=req.skip_vlm,
            input_mode=req.input_mode,
            project_id=req.project_id,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise safe_internal_error(exc, context="copilot") from exc

    job = result.get("job")
    job_resp = JobResponse(**job) if job else None
    return CopilotTurnResponse(
        intent=result["intent"],
        reply=result["reply"],
        job=job_resp,
        artifact=result.get("artifact"),
        artifact_id=result.get("artifact_id"),
        copilot_model=result.get("copilot_model") or settings.copilot_model,
        diagram_type=result.get("diagram_type") or req.diagram_type,
    )
