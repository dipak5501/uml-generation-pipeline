"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import agent, analytics, artifacts, generate, human_review
from app.security import cors_allow_origins
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    try:
        from sqlmodel import Session

        from app.db import get_engine
        from app.services.job_maintenance import reap_stale_jobs

        with Session(get_engine()) as session:
            # All in-process workers die with the process — reap every incomplete job.
            reap_stale_jobs(session, max_age_minutes=None)
    except Exception:
        logger.exception("Stale job reaper failed (non-fatal)")
    if not (settings.api_access_token or "").strip():
        logger.warning(
            "API_ACCESS_TOKEN is unset — API is open. Set a token before public deploy."
        )
    logger.info("UML app ready (provider=%s)", settings.provider_name)
    yield


app = FastAPI(
    title="UML-Pipeline API",
    version="1.0.0",
    lifespan=lifespan,
)
_origins = cors_allow_origins()
# Browsers reject Access-Control-Allow-Origin: * together with credentials.
_allow_credentials = _origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(artifacts.router)
app.include_router(human_review.router)
app.include_router(analytics.router)
app.include_router(agent.router)


@app.get("/")
def root():
    return {
        "name": get_settings().app_name,
        "docs": "/docs",
        "health": "/api/settings/health",
        "remote_agent": "/api/agent/health",
    }
