"""Thesis briefing, snapshot, and 0–6 human reviews."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.models import HumanReview
from app.services.thesis import DEMO_CASES, human_score_on_six

os.environ["MOCK_PROVIDERS"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
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


def test_briefing_and_snapshot(client):
    gen = client.post(
        "/api/generate",
        json={
            "requirement": "Campus parking office with permits and citations.",
            "diagram_type": "class",
            "async_mode": False,
        },
    )
    assert gen.status_code == 200, gen.text

    briefing = client.get("/api/thesis/briefing")
    assert briefing.status_code == 200, briefing.text
    body = briefing.json()
    assert body["live"]["n"] >= 1
    assert "RQ1" in {rq["id"] for rq in body["research_questions"]}
    assert len(body["demo_cases"]) == len(DEMO_CASES)
    assert body["formula"]["dataset"]

    snap = client.get("/api/thesis/snapshot", params={"fmt": "json", "seed": 42, "n_per_type": 10})
    assert snap.status_code == 200, snap.text
    payload = snap.json()
    assert payload["seed"] == 42
    assert payload["actual_n"] >= 1
    assert payload["items"][0]["diagram_type"] in {"class", "object", "component", "package"}

    csv = client.get("/api/thesis/snapshot", params={"fmt": "csv", "seed": 42, "n_per_type": 10})
    assert csv.status_code == 200
    assert b"composite_score" in csv.content


def test_human_review_zero_to_six(client):
    gen = client.post(
        "/api/generate",
        json={"requirement": "Library loans and members", "diagram_type": "object", "async_mode": False},
    )
    artifact_id = gen.json()["artifact"]["id"]
    hr = client.post(
        "/api/human-review",
        json={
            "artifact_id": artifact_id,
            "reviewer_name": "Committee",
            "reviewer_role": "advisor",
            "semantic_correctness": 0,
            "structural_completeness": 6,
            "syntactic_accuracy": 5,
            "overall_coherence": 4,
            "score_scale": 6,
        },
    )
    assert hr.status_code == 200, hr.text
    assert hr.json()["score_scale"] == 6
    assert hr.json()["mean_score"] == 3.75

    summary = client.get("/api/analytics/summary").json()
    assert summary["human_review_count"] >= 1
    assert "human_vs_ai_n" in summary
    by_object = (summary.get("by_diagram_type") or {}).get("object") or {}
    assert "majority" in by_object
    assert "dataset" in by_object


def test_legacy_five_scale_maps_to_six():
    review = HumanReview(
        artifact_id=1,
        reviewer_id=1,
        semantic_correctness=1,
        structural_completeness=5,
        syntactic_accuracy=5,
        overall_coherence=5,
        score_scale=5,
    )
    # mean 4.0 on 1–5 → (4-1)*(6/4) = 4.5 on 0–6
    assert abs(human_score_on_six(review) - 4.5) < 1e-9


def test_skip_repair_generate(client):
    r = client.post(
        "/api/generate",
        json={
            "requirement": "Fleet vehicles and routes",
            "diagram_type": "component",
            "async_mode": False,
            "skip_repair": True,
            "skip_majority": True,
        },
    )
    assert r.status_code == 200, r.text
    art = r.json()["artifact"]
    assert art["composite_score"] >= 0
    msgs = art.get("validation_messages") or ""
    assert "repair loop off" in msgs
