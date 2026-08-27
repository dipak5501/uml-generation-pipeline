"""Remote command agent API — control the Mac Studio server from any network."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas import AgentCommandRequest, AgentCommandResponse, AgentHealthResponse, AgentTaskResponse
from app.security import require_remote_agent_access
from app.services.remote_agent import (
    agent_health_snapshot,
    get_task,
    list_tasks,
    submit_command,
    task_to_dict,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.get("/health", response_model=AgentHealthResponse)
def agent_health():
    return AgentHealthResponse(**agent_health_snapshot())


@router.post("/command", response_model=AgentCommandResponse)
def run_command(
    body: AgentCommandRequest,
    request: Request,
    _: None = Depends(require_remote_agent_access),
):
    try:
        task = submit_command(
            body.command,
            args=body.args,
            client_key=_client_key(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=429 if "Rate limit" in str(exc) else 400, detail=str(exc)) from exc
    return AgentCommandResponse(
        task_id=task.id,
        command=task.command,
        status=task.status,
    )


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
def task_status(
    task_id: str,
    _: None = Depends(require_remote_agent_access),
):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse(**task_to_dict(task))


@router.get("/tasks", response_model=list[AgentTaskResponse])
def task_list(
    limit: int = 20,
    _: None = Depends(require_remote_agent_access),
):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    return [AgentTaskResponse(**task_to_dict(t)) for t in list_tasks(limit=limit)]
