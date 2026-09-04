"""Tests for UML Copilot intent routing and API (mock providers)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["MOCK_PROVIDERS"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"

from app.services.copilot import detect_intent, resolve_intent


def test_detect_intent_generate():
    assert detect_intent("Generate a class diagram for a bookstore checkout", has_artifact=False) == "generate"
    assert detect_intent("Please create a UML diagram for checkout", has_artifact=False) == "generate"


def test_detect_intent_correct():
    assert detect_intent("Add a Payment class and link it to Order", has_artifact=True) == "correct"
    assert detect_intent("Fix the missing association to Customer", has_artifact=True) == "correct"


def test_detect_intent_chat():
    assert detect_intent("What diagram types do you support?", has_artifact=False) == "chat"
    # Vague descriptions stay in chat so the copilot can ask clarifying questions.
    assert detect_intent("Online bookstore with carts and inventory", has_artifact=False) == "chat"
    assert detect_intent("Campus parking permits", has_artifact=False) == "chat"


def test_resolve_intent_forced():
    assert resolve_intent("hello", "generate", has_artifact=False) == "generate"
    assert resolve_intent("add X", "correct", has_artifact=False) == "chat"


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


def test_copilot_health(client):
    r = client.get("/api/copilot/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "copilot_model" in body
    assert "generation_provider" in body


def test_copilot_chat_turn(client):
    r = client.post(
        "/api/copilot/turn",
        json={"message": "What can you do?", "action": "chat", "diagram_type": "class"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "chat"
    assert body["reply"]


def test_copilot_generate_turn(client):
    r = client.post(
        "/api/copilot/turn",
        json={
            "message": "Bookstore with books, carts, and checkout orders.",
            "action": "generate",
            "diagram_type": "class",
            "skip_vlm": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "generate"
    assert body["job"] is not None
    assert body["job"]["id"] > 0


def test_copilot_correct_requires_artifact(client):
    r = client.post(
        "/api/copilot/turn",
        json={"message": "Add a Payment class", "action": "correct", "diagram_type": "class"},
    )
    # Without artifact, correct downgrades to generate if message is long enough
    assert r.status_code == 200, r.text
    assert r.json()["intent"] in ("generate", "chat")
