"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import analytics, artifacts, generate, human_review
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("UML app ready (provider=%s)", settings.provider_name)
    yield


app = FastAPI(
    title="UML-Pipeline API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(artifacts.router)
app.include_router(human_review.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    return {
        "name": get_settings().app_name,
        "docs": "/docs",
        "health": "/api/settings/health",
    }
