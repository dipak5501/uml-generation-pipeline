"""Optional API access control and safe error helpers.

When ``API_ACCESS_TOKEN`` is set, mutating and export endpoints require
``Authorization: Bearer <token>`` or ``X-API-Key: <token>``.
When unset (local demo default), endpoints remain open and health reports a warning.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Request

from app.settings import get_settings

logger = logging.getLogger(__name__)

# Hard caps shared by routers / schemas
MAX_REQUIREMENT_CHARS = 50_000
MAX_SAMPLES_LIMIT = 200
MAX_BATCH_ITEMS = 1_000


def access_token_configured() -> bool:
    return bool((get_settings().api_access_token or "").strip())


def _extract_presented_token(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
        if len(parts) == 1 and parts[0].strip():
            return parts[0].strip()
    return None


async def require_api_access(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Enforce API token when configured; no-op for open local demos."""
    expected = (get_settings().api_access_token or "").strip()
    if not expected:
        return
    presented = _extract_presented_token(authorization, x_api_key)
    if presented is None or not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def safe_internal_error(exc: Exception, *, context: str = "request") -> HTTPException:
    """Log full exception; return a non-leaking HTTP 500."""
    logger.exception("Unhandled error during %s", context)
    return HTTPException(status_code=500, detail="Internal server error")


def resolve_artifact_image(image_path: str | None, artifact_dir: Path) -> Path | None:
    """Return path only if it resolves inside ``artifact_dir`` and exists."""
    if not image_path:
        return None
    try:
        root = artifact_dir.resolve()
        candidate = Path(image_path).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        logger.warning("Rejected image path outside artifact_dir: %s", image_path)
        return None
    if not candidate.is_file():
        return None
    return candidate


def cors_allow_origins() -> list[str]:
    raw = (get_settings().cors_origins or "").strip()
    if not raw or raw == "*":
        # Wildcard without credentials is OK for open demos; never pair with credentials.
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
