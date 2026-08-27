from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.schemas import AnalyticsSummary, HealthResponse
from app.security import access_token_configured, require_api_access
from app.services.analytics import analytics_summary, export_dataset, score_distributions
from app.services.package_failures import package_failure_report
from app.settings import get_settings

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
def summary(session: Session = Depends(get_session)):
    data = analytics_summary(session)
    return AnalyticsSummary(**data)


@router.get("/analytics/distributions")
def distributions(session: Session = Depends(get_session)):
    return score_distributions(session)


@router.get("/analytics/package-failures")
def package_failures(session: Session = Depends(get_session)):
    return package_failure_report(session)


@router.get("/export/dataset")
def export(
    fmt: str = Query(default="jsonl"),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    if fmt not in {"jsonl", "csv", "parquet"}:
        fmt = "jsonl"
    body, media, filename = export_dataset(session, fmt=fmt)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/adaptation/status")
def adaptation_status():
    from app.services.adaptation import AdaptationMemory

    return AdaptationMemory().snapshot()


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
        messages.append(
            f"USE_OLLAMA=true — LLaMA-Vision at {settings.ollama_base_url}; "
            f"Qwen2.5-VL at {settings.ollama_qwen_base_url}"
        )
        messages.append(f"VLM ensemble: {settings.vlm_models}")
        aya_backend = (settings.vlm_aya_backend or "ollama_standin").strip().lower()
        if aya_backend in {"local", "transformers", "mps", "local_transformers"}:
            messages.append(
                f"Aya-Vision-8B backend: local transformers ({settings.aya_vlm_model}) — paper-exact"
            )
        elif aya_backend in {"ollama_standin", "ollama", "standin", ""}:
            messages.append(
                "Aya-Vision-8B backend: llava:7b stand-in (not paper-exact). "
                "Set VLM_AYA_BACKEND=local for paper-exact Aya on this Mac."
            )
        elif aya_backend in {"hf", "huggingface"}:
            messages.append(f"Aya-Vision backend: Hugging Face ({settings.aya_vlm_model})")
        else:
            messages.append(
                f"Aya-Vision backend: openai_compat ({settings.aya_vlm_model} @ "
                f"{settings.aya_vlm_base_url or 'AYA_VLM_BASE_URL unset'})"
            )
        if settings.vlm_fast_mode:
            messages.append("VLM_FAST_MODE=true — only the first VLM scores (not paper ensemble)")

    adapter_ok = Path(settings.finetuned_adapter_path).exists()
    if settings.use_finetuned_code:
        if adapter_ok:
            messages.append(f"USE_FINETUNED_CODE=true — PlantUML via LoRA adapter at {settings.finetuned_adapter_path}")
        else:
            messages.append(
                f"USE_FINETUNED_CODE=true but adapter missing at {settings.finetuned_adapter_path} "
                "(run: python scripts/finetune_plantuml.py)"
            )

    if not access_token_configured():
        messages.append(
            "API_ACCESS_TOKEN unset — generate/export/repair endpoints are open; "
            "set a token before public internet exposure"
        )
    else:
        messages.append("API_ACCESS_TOKEN configured — protected endpoints require Bearer/X-API-Key")

    if os.getenv("PLANTUML_REMOTE", "true").lower() in ("1", "true", "yes"):
        messages.append(
            "PLANTUML_REMOTE=true — diagram text is sent to the configured PlantUML HTTP server"
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
        auth_required=access_token_configured(),
        remote_agent_available=True,
        messages=messages,
    )
