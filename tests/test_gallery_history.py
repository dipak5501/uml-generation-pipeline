"""Restored live diagrams appear in Generated Diagrams."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["MOCK_PROVIDERS"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["UML_SKIP_GALLERY_HISTORY"] = "1"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    monkeypatch.setenv("UML_SKIP_GALLERY_HISTORY", "1")
    from app.settings import get_settings
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None

    from app.main import app
    from app.db import init_db

    init_db()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    dbmod._engine = None


def test_import_restores_png_and_scores(client, tmp_path):
    from sqlmodel import Session

    from app.db import get_engine
    from app.services.gallery_history import import_gallery_history
    from app.settings import ROOT, get_settings

    catalog = ROOT / "sample_data" / "gallery_history" / "catalog.json"
    assert catalog.is_file()
    png = ROOT / "sample_data" / "gallery_history" / "pngs" / "504.png"
    assert png.is_file() and png.stat().st_size > 1000

    settings = get_settings()
    dest = Path(settings.artifact_dir)
    dest.mkdir(parents=True, exist_ok=True)
    with Session(get_engine()) as session:
        first = import_gallery_history(session, catalog_path=catalog, artifact_dir=dest)
        second = import_gallery_history(session, catalog_path=catalog, artifact_dir=dest)

    assert 504 in first["inserted"]
    assert 512 in first["inserted"]
    assert 480 in first["inserted"]
    assert 504 in second["skipped"]
    assert not second["inserted"]

    listed = client.get("/api/artifacts/library", params={"limit": 50})
    assert listed.status_code == 200, listed.text
    body = listed.json()
    ids = {item["id"] for item in body["items"]}
    assert {504, 506, 509, 511, 505, 480, 477} <= ids

    detail = client.get("/api/artifacts/504")
    assert detail.status_code == 200
    data = detail.json()
    assert data["diagram_type"] == "class"
    assert data["dataset_accepted"] is True
    assert len(data["model_scores"]) == 3
    img = client.get("/api/artifacts/504/image")
    assert img.status_code == 200
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

    java = client.get("/api/artifacts/480")
    assert java.status_code == 200
    assert java.json()["input_mode"] == "source_code"
    assert java.json()["source_language"] == "java"
