from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.schemas import AnalyticsSummary, HealthResponse
from app.services.analytics import analytics_summary, export_dataset, score_distributions
from app.settings import get_settings

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
def summary(session: Session = Depends(get_session)):
    data = analytics_summary(session)
    return AnalyticsSummary(**data)


@router.get("/analytics/distributions")
def distributions(session: Session = Depends(get_session)):
    return score_distributions(session)


@router.get("/export/dataset")
def export(fmt: str = Query(default="jsonl"), session: Session = Depends(get_session)):
    if fmt not in {"jsonl", "csv", "parquet"}:
        fmt = "jsonl"
    body, media, filename = export_dataset(session, fmt=fmt)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/settings/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)):
    settings = get_settings()
    messages: list[str] = []
    database_ok = True
    try:
        session.connection()
    except Exception as exc:
        database_ok = False
        messages.append(f"Database error: {exc}")

    jar_ok = settings.plantuml_jar.is_file()
    if not jar_ok:
        messages.append(f"PlantUML jar missing at {settings.plantuml_jar} (will auto-download on first render)")

    java_ok = shutil.which("java") is not None
    if not java_ok:
        messages.append("Java JDK not found on PATH — rendering will fail until installed")
    else:
        try:
            subprocess.run(["java", "-version"], capture_output=True, timeout=10, check=False)
        except Exception as exc:
            java_ok = False
            messages.append(f"Java check failed: {exc}")

    if settings.mock_providers:
        messages.append("MOCK_PROVIDERS=true — using deterministic mock LLM/VLM responses")

    status = "ok" if database_ok else "degraded"
    if not java_ok:
        status = "degraded"

    return HealthResponse(
        status=status,
        provider=settings.provider_name,
        mock_providers=settings.mock_providers,
        database_ok=database_ok,
        plantuml_jar_present=jar_ok,
        java_available=java_ok,
        messages=messages,
    )
