"""Remote command agent API tests."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    monkeypatch.setenv("REMOTE_AGENT_TOKEN", "")
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


@pytest.fixture()
def locked_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'locked.db'}")
    monkeypatch.setenv("API_ACCESS_TOKEN", "agent-secret")
    monkeypatch.setenv("REMOTE_AGENT_TOKEN", "")
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


def test_agent_health_open(client):
    r = client.get("/api/agent/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "health" in body["allowed_commands"]
    assert body["auth_required"] is False


@patch("app.services.remote_agent._fetch_health")
def test_command_requires_token_when_configured(mock_health, locked_client):
    mock_health.return_value = {"status": "ok", "mock_providers": True}
    r = locked_client.post("/api/agent/command", json={"command": "health"})
    assert r.status_code == 401

    r = locked_client.post(
        "/api/agent/command",
        headers={"Authorization": "Bearer agent-secret"},
        json={"command": "health"},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]
    for _ in range(40):
        status = locked_client.get(
            f"/api/agent/tasks/{task_id}",
            headers={"Authorization": "Bearer agent-secret"},
        )
        assert status.status_code == 200
        if status.json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert status.json()["status"] == "completed"
    assert status.json()["result"] is not None


def test_rejects_unknown_command(client):
    r = client.post("/api/agent/command", json={"command": "rm -rf /"})
    assert r.status_code == 400


@patch("app.services.remote_agent._fetch_health")
def test_health_command_completes(mock_health, client):
    mock_health.return_value = {"status": "ok", "mock_providers": True}
    r = client.post("/api/agent/command", json={"command": "health"})
    assert r.status_code == 200
    task_id = r.json()["task_id"]
    for _ in range(40):
        task = client.get(f"/api/agent/tasks/{task_id}").json()
        if task["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert task["status"] == "completed"
    assert task["result"]["status"] == "ok"


@patch("app.services.remote_agent._training_status")
def test_training_status_command(mock_training, client):
    mock_training.return_value = {"adapter_present": True, "finetune_running": False}
    r = client.post("/api/agent/command", json={"command": "training-status"})
    task_id = r.json()["task_id"]
    for _ in range(40):
        task = client.get(f"/api/agent/tasks/{task_id}").json()
        if task["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert task["status"] == "completed"
    assert task["result"]["adapter_present"] is True


def test_list_tasks(client):
    client.post("/api/agent/command", json={"command": "training-status"})
    r = client.get("/api/agent/tasks", params={"limit": 5})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
