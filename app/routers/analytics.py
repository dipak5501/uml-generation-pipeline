from __future__ import annotations

from pathlib import Path

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

    from uml_pipeline.render import java_runtime_ok

    java_ok = java_runtime_ok()
    if not java_ok:
        messages.append(
            "No usable local Java JDK — renders use the PlantUML HTTP server fallback "
            "(set PLANTUML_REMOTE=false to disable)."
        )

    if settings.mock_providers:
        messages.append("MOCK_PROVIDERS=true — using deterministic mock LLM/VLM responses")
    elif settings.use_hf_inference:
        messages.append(
            f"USE_HF_INFERENCE=true — spec={settings.spec_model} · code={settings.code_model}"
        )
        if not (settings.hf_token or settings.openai_api_key):
            messages.append("HF_TOKEN is empty — set it before generating with live models")
    elif settings.use_ollama:
        messages.append(f"USE_OLLAMA=true — Ollama at {settings.ollama_base_url}")

    adapter_ok = Path(settings.finetuned_adapter_path).exists()
    if settings.use_finetuned_code:
        if adapter_ok:
            messages.append(f"USE_FINETUNED_CODE=true — PlantUML via LoRA adapter at {settings.finetuned_adapter_path}")
        else:
            messages.append(
                f"USE_FINETUNED_CODE=true but adapter missing at {settings.finetuned_adapter_path} "
                "(run: python scripts/finetune_plantuml.py)"
            )

    status = "ok" if database_ok else "degraded"

    return HealthResponse(
        status=status,
        provider=settings.provider_name,
        provider_summary=settings.provider_summary,
        mock_providers=settings.mock_providers,
        use_finetuned_code=settings.use_finetuned_code,
        finetuned_adapter_path=str(settings.finetuned_adapter_path),
        finetuned_adapter_present=adapter_ok,
        database_ok=database_ok,
        plantuml_jar_present=jar_ok,
        java_available=java_ok,
        messages=messages,
    )
