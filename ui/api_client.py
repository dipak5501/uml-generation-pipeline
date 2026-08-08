"""Shared HTTP helpers for Streamlit UI."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _auth_headers() -> dict[str, str]:
    token = (os.getenv("API_ACCESS_TOKEN") or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def api_get(path: str, **params) -> Any:
    with httpx.Client(base_url=API_BASE, timeout=120.0, headers=_auth_headers()) as client:
        r = client.get(path, params=params or None)
        r.raise_for_status()
        if "application/json" in r.headers.get("content-type", ""):
            return r.json()
        return r.content


def api_post(path: str, payload: dict) -> Any:
    with httpx.Client(base_url=API_BASE, timeout=600.0, headers=_auth_headers()) as client:
        r = client.post(path, json=payload)
        r.raise_for_status()
        return r.json()


def api_get_bytes(path: str) -> bytes:
    with httpx.Client(base_url=API_BASE, timeout=120.0, headers=_auth_headers()) as client:
        r = client.get(path)
        r.raise_for_status()
        return r.content
