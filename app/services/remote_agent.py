"""Remote command agent — queued shell tasks and optional Cursor SDK prompts."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from app.settings import ROOT, get_settings

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="remote-agent")
_lock = threading.Lock()
_tasks: dict[str, "AgentTask"] = {}
_rate_buckets: dict[str, deque[float]] = {}
_MAX_TASKS = 200
_RATE_WINDOW_SEC = 60.0

ALLOWED_COMMANDS = frozenset(
    {
        "health",
        "restart-api",
        "restart-ui",
        "smoke-test",
        "generate",
        "training-status",
        "server-status",
        "agent-prompt",
    }
)


@dataclass
class AgentTask:
    id: str
    command: str
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    output: str = ""
    error: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _prune_tasks() -> None:
    if len(_tasks) <= _MAX_TASKS:
        return
    finished = sorted(
        (t for t in _tasks.values() if t.status in {"completed", "failed"}),
        key=lambda t: t.finished_at or t.created_at,
    )
    for task in finished[: len(_tasks) - _MAX_TASKS]:
        _tasks.pop(task.id, None)


def _check_rate_limit(client_key: str, limit: int) -> None:
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        bucket = _rate_buckets.setdefault(client_key, deque())
        while bucket and now - bucket[0] > _RATE_WINDOW_SEC:
            bucket.popleft()
        if len(bucket) >= limit:
            raise ValueError("Rate limit exceeded — try again in a minute")
        bucket.append(now)


def _run_script(rel_path: str, timeout: int = 600) -> tuple[int, str]:
    script = (ROOT / rel_path).resolve()
    root_resolved = ROOT.resolve()
    try:
        script.relative_to(root_resolved)
    except ValueError as exc:
        return 1, f"Script path outside project root: {rel_path}"
    if not script.is_file():
        return 1, f"Script not found: {rel_path}"
    proc = subprocess.run(
        ["bash", str(script)] if script.suffix == ".sh" else ["python3", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def _fetch_health() -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.api_base_url.rstrip('/')}/api/settings/health"
    with httpx.Client(timeout=15.0) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def _training_status() -> dict[str, Any]:
    settings = get_settings()
    adapter = Path(settings.finetuned_adapter_path)
    meta_path = adapter / "finetune_meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {"error": "invalid finetune_meta.json"}

    finetune_pids: list[str] = []
    try:
        out = subprocess.run(
            ["pgrep", "-lf", "finetune_plantuml.py"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        finetune_pids = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass

    return {
        "adapter_path": str(adapter),
        "adapter_present": adapter.is_dir() and any(adapter.iterdir()) if adapter.exists() else False,
        "finetune_meta": meta,
        "finetune_running": bool(finetune_pids),
        "finetune_processes": finetune_pids[:5],
        "use_finetuned_code": settings.use_finetuned_code,
    }


def _run_generate(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    payload = {
        "requirement": args.get(
            "requirement",
            "Remote agent test: bookstore with carts, orders, and inventory.",
        ),
        "diagram_type": args.get("diagram_type", "class"),
        "input_mode": args.get("input_mode", "requirement"),
        "async_mode": bool(args.get("async_mode", False)),
        "skip_vlm": bool(args.get("skip_vlm", True)),
    }
    headers: dict[str, str] = {}
    token = (settings.api_access_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{settings.api_base_url.rstrip('/')}/api/generate"
    with httpx.Client(timeout=300.0) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()


def _run_cursor_prompt(prompt: str) -> dict[str, Any]:
    api_key = (get_settings().cursor_api_key or os.getenv("CURSOR_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "CURSOR_API_KEY not configured — set it in .env to command Cursor agents remotely"
        )
    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise RuntimeError(
            "cursor-sdk not installed — pip install cursor-sdk to enable agent-prompt"
        ) from exc

    result = Agent.prompt(
        prompt,
        AgentOptions(
            api_key=api_key,
            model="composer-2.5",
            local=LocalAgentOptions(cwd=str(ROOT)),
        ),
    )
    return {
        "status": result.status,
        "result": result.result,
        "agent_id": getattr(result, "agent_id", None),
    }


def _execute_command(command: str, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    handlers: dict[str, Callable[[], tuple[dict[str, Any], str]]] = {
        "health": lambda: (_fetch_health(), "health check ok"),
        "restart-api": lambda: _script_result("scripts/restart_api.sh", 120),
        "restart-ui": lambda: _script_result("scripts/restart_ui.sh", 120),
        "smoke-test": lambda: _script_result("scripts/smoke_test.py", 900),
        "server-status": lambda: _script_result("scripts/macos_server_status.sh", 60),
        "training-status": lambda: (_training_status(), "training status collected"),
        "generate": lambda: (_run_generate(args), "generation complete"),
        "agent-prompt": lambda: (
            _run_cursor_prompt(str(args.get("prompt") or args.get("text") or "")),
            "cursor agent finished",
        ),
    }
    if command not in handlers:
        raise ValueError(f"Unknown command: {command}")
    if command == "agent-prompt" and not (args.get("prompt") or args.get("text")):
        raise ValueError("agent-prompt requires a non-empty prompt")
    return handlers[command]()


def _script_result(rel_path: str, timeout: int) -> tuple[dict[str, Any], str]:
    code, output = _run_script(rel_path, timeout=timeout)
    if code != 0:
        raise RuntimeError(output or f"{rel_path} exited {code}")
    return {"exit_code": code, "output": output[-8000:]}, output[-4000:]


def _worker(task_id: str, command: str, args: dict[str, Any]) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = _utcnow()

    try:
        result, output = _execute_command(command, args)
        with _lock:
            task = _tasks[task_id]
            task.status = "completed"
            task.result = result
            task.output = output
            task.finished_at = _utcnow()
    except Exception as exc:
        logger.exception("Remote agent task %s failed", task_id)
        with _lock:
            task = _tasks[task_id]
            task.status = "failed"
            task.error = str(exc)
            task.finished_at = _utcnow()


def submit_command(
    command: str,
    *,
    args: dict[str, Any] | None = None,
    client_key: str = "default",
) -> AgentTask:
    command = (command or "").strip().lower()
    if command not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Command not allowed: {command!r}. Allowed: {sorted(ALLOWED_COMMANDS)}"
        )
    settings = get_settings()
    _check_rate_limit(client_key, settings.remote_agent_rate_limit)

    task_id = uuid.uuid4().hex[:12]
    task = AgentTask(id=task_id, command=command)
    with _lock:
        _tasks[task_id] = task
        _prune_tasks()

    payload = dict(args or {})
    _executor.submit(_worker, task_id, command, payload)
    return task


def get_task(task_id: str) -> AgentTask | None:
    with _lock:
        return _tasks.get(task_id)


def list_tasks(limit: int = 20) -> list[AgentTask]:
    with _lock:
        items = sorted(_tasks.values(), key=lambda t: t.created_at, reverse=True)
    return items[:limit]


def agent_health_snapshot() -> dict[str, Any]:
    settings = get_settings()
    token = (settings.remote_agent_token or settings.api_access_token or "").strip()
    cursor_key = (settings.cursor_api_key or os.getenv("CURSOR_API_KEY") or "").strip()
    cursor_sdk = False
    try:
        import cursor_sdk  # noqa: F401

        cursor_sdk = True
    except ImportError:
        pass
    with _lock:
        active = sum(1 for t in _tasks.values() if t.status in {"queued", "running"})
    return {
        "status": "ok",
        "agent": "uml-pipeline-remote-agent",
        "version": "1.0.0",
        "auth_required": bool(token),
        "cursor_sdk_available": cursor_sdk,
        "cursor_agent_enabled": bool(cursor_key and cursor_sdk),
        "allowed_commands": sorted(ALLOWED_COMMANDS),
        "active_tasks": active,
        "rate_limit_per_minute": settings.remote_agent_rate_limit,
    }


def task_to_dict(task: AgentTask) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "command": task.command,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "result": task.result,
        "output": task.output[-8000:] if task.output else "",
        "error": task.error,
    }
