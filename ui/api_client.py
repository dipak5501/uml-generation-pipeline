"""Shared HTTP helpers for Streamlit UI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
# LaunchAgents source .env before Streamlit starts; this covers `streamlit run` too.
load_dotenv(_ROOT / ".env", override=False)


def _resolve_api_base() -> str:
    """Streamlit→API must be reachable from this host (usually localhost).

    Never use a trycloudflare hostname here: campus DNS often cannot resolve it
    and yields Errno 8. Public tunnel URLs belong in PUBLIC_API_URL only.
    """
    raw = (os.getenv("API_BASE_URL") or "http://127.0.0.1:8000").strip().rstrip("/")
    if "trycloudflare.com" in raw.lower() or not raw:
        return "http://127.0.0.1:8000"
    return raw


API_BASE = _resolve_api_base()
# Browser-facing links (exports/docs); optional; never used for server-side HTTP.
PUBLIC_API_BASE = (os.getenv("PUBLIC_API_URL") or "").strip().rstrip("/")


def _auth_headers() -> dict[str, str]:
    token = (os.getenv("API_ACCESS_TOKEN") or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "X-API-Key": token}


def api_auth_mismatch_message() -> str | None:
    """Warn when the API expects a token but this UI process has none."""
    if (os.getenv("API_ACCESS_TOKEN") or "").strip():
        return None
    try:
        with httpx.Client(base_url=API_BASE, timeout=5.0) as client:
            r = client.get("/api/settings/health")
            if not r.is_success:
                return None
            msgs = r.json().get("messages") or []
            if any("API_ACCESS_TOKEN configured" in str(m) for m in msgs):
                return (
                    "API requires API_ACCESS_TOKEN but Streamlit has none (or a different value). "
                    "Set the same token in .env on this Mac, then restart API and UI."
                )
    except Exception:
        return None
    return None


def _format_http_error(response: httpx.Response) -> str:
    """Turn FastAPI/httpx failures into short UI-facing messages."""
    if response.status_code == 401:
        return (
            "401 Unauthorized — rescore needs API_ACCESS_TOKEN. "
            "Set the same value in .env for API and Streamlit, then restart both services."
        )
    try:
        data = response.json()
    except Exception:
        text = (response.text or "").strip()
        return f"{response.status_code}: {text[:300]}" if text else f"HTTP {response.status_code}"

    detail = data.get("detail", data) if isinstance(data, dict) else data
    if isinstance(detail, str):
        return f"{response.status_code}: {detail}"
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            loc = ".".join(str(x) for x in (item.get("loc") or ()) if x != "body")
            msg = str(item.get("msg") or item)
            parts.append(f"{loc}: {msg}" if loc else msg)
        if parts:
            return f"{response.status_code}: " + "; ".join(parts)
    return f"{response.status_code}: {detail}"


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    raise httpx.HTTPStatusError(
        _format_http_error(response),
        request=response.request,
        response=response,
    )


def api_get(path: str, **params) -> Any:
    with httpx.Client(base_url=API_BASE, timeout=120.0, headers=_auth_headers()) as client:
        r = client.get(path, params=params or None)
        _raise_for_status(r)
        if "application/json" in r.headers.get("content-type", ""):
            return r.json()
        return r.content


def api_post(path: str, payload: dict) -> Any:
    with httpx.Client(base_url=API_BASE, timeout=600.0, headers=_auth_headers()) as client:
        r = client.post(path, json=payload)
        _raise_for_status(r)
        return r.json()


def api_get_bytes(path: str) -> bytes:
    with httpx.Client(base_url=API_BASE, timeout=120.0, headers=_auth_headers()) as client:
        r = client.get(path)
        _raise_for_status(r)
        return r.content
