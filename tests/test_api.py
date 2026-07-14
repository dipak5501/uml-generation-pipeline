"""API integration tests with mock providers."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force mock mode before app import side effects
os.environ["MOCK_PROVIDERS"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    # Reset cached settings + engine
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


def test_health(client):
    r = client.get("/api/settings/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mock_providers"] is True
    assert body["database_ok"] is True


def test_generate_class_artifact(client):
    r = client.post(
        "/api/generate",
        json={
            "requirement": "Online bookstore with books, carts, and checkout orders.",
            "diagram_type": "class",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "artifact" in data
    art = data["artifact"]
    assert art["diagram_type"] == "class"
    assert "@startuml" in art["plantuml_code"].lower()
    assert "model_scores" in art
    assert isinstance(art["composite_score"], (int, float))


@pytest.mark.parametrize(
    "diagram_type", ["class", "object", "component", "package", "flowchart"]
)
def test_e2e_each_diagram_type(client, diagram_type):
    r = client.post(
        "/api/generate",
        json={
            "requirement": "Hospital appointments with patients, doctors, and clinics.",
            "diagram_type": diagram_type,
        },
    )
    assert r.status_code == 200, r.text
    art = r.json()["artifact"]
    assert art["diagram_type"] == diagram_type
    # Render may succeed if Java present; either way score defined
    assert art["composite_score"] >= 0
    if art["render_status"] != "success":
        assert art["composite_score"] == 0


def test_human_review_and_analytics(client):
    gen = client.post(
        "/api/generate",
        json={"requirement": "Fleet logistics routes and vehicles", "diagram_type": "component"},
    )
    assert gen.status_code == 200
    artifact_id = gen.json()["artifact"]["id"]

    hr = client.post(
        "/api/human-review",
        json={
            "artifact_id": artifact_id,
            "reviewer_name": "Test Reviewer",
            "reviewer_role": "expert",
            "semantic_correctness": 4,
            "structural_completeness": 5,
            "syntactic_accuracy": 4,
            "overall_coherence": 4,
            "comments": "Looks coherent",
        },
    )
    assert hr.status_code == 200
    assert hr.json()["mean_score"] == 4.25

    summary = client.get("/api/analytics/summary")
    assert summary.status_code == 200
    assert summary.json()["total_artifacts"] >= 1
    assert summary.json()["human_review_count"] >= 1

    export = client.get("/api/export/dataset?fmt=jsonl")
    assert export.status_code == 200
    assert b"diagram_type" in export.content


def test_list_and_get_artifact(client):
    gen = client.post(
        "/api/generate",
        json={"requirement": "LMS courses and quizzes", "diagram_type": "object"},
    )
    aid = gen.json()["artifact"]["id"]
    listed = client.get("/api/artifacts")
    assert any(a["id"] == aid for a in listed.json())
    detail = client.get(f"/api/artifacts/{aid}")
    assert detail.status_code == 200
    puml = client.get(f"/api/artifacts/{aid}/plantuml")
    assert puml.status_code == 200
    assert b"@startuml" in puml.content.lower()
