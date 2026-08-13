"""Security and input-hardening tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
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
    monkeypatch.setenv("API_ACCESS_TOKEN", "test-secret-token")
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
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)


def test_samples_limit_capped(client):
    r = client.get("/api/samples", params={"limit": 999999})
    assert r.status_code == 422


def test_generate_rejects_oversized_requirement(client):
    r = client.post(
        "/api/generate",
        json={"requirement": "x" * 50_001, "diagram_type": "class"},
    )
    assert r.status_code == 422


def test_batch_rejects_too_many_items(client):
    r2 = client.post(
        "/api/generate/batch",
        json={
            "n_samples": 201,
            "diagram_types": ["class", "object", "component", "package"],
            "use_sample_file": True,
        },
    )
    assert r2.status_code == 422
    assert "artifacts" in r2.text.lower() or "limit" in r2.text.lower() or "n_samples" in r2.text.lower()


def test_api_token_required_when_configured(locked_client):
    r = locked_client.post(
        "/api/generate",
        json={"requirement": "Bookstore with carts and orders", "diagram_type": "class"},
    )
    assert r.status_code == 401

    r = locked_client.post(
        "/api/generate",
        headers={"Authorization": "Bearer test-secret-token"},
        json={"requirement": "Bookstore with carts and orders", "diagram_type": "class"},
    )
    assert r.status_code == 200, r.text

    r = locked_client.get("/api/export/dataset")
    assert r.status_code == 401
    r = locked_client.get(
        "/api/export/dataset",
        headers={"X-API-Key": "test-secret-token"},
    )
    assert r.status_code == 200


def test_health_warns_when_token_unset(client):
    r = client.get("/api/settings/health")
    assert r.status_code == 200
    msgs = " ".join(r.json().get("messages") or [])
    assert "API_ACCESS_TOKEN unset" in msgs


def test_resolve_artifact_image_blocks_escape(tmp_path):
    from app.security import resolve_artifact_image

    root = tmp_path / "artifacts"
    root.mkdir()
    inside = root / "1" / "diagram.png"
    inside.parent.mkdir()
    inside.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")

    assert resolve_artifact_image(str(inside), root) == inside.resolve()
    assert resolve_artifact_image(str(outside), root) is None
    assert resolve_artifact_image(str(root / ".." / "secret.txt"), root) is None


def test_invalid_plantuml_server_url_rejected(monkeypatch):
    from uml_pipeline.render import render_plantuml_remote

    monkeypatch.setenv("PLANTUML_REMOTE", "true")
    monkeypatch.setenv("PLANTUML_SERVER_URL", "file:///etc/passwd")
    img, err = render_plantuml_remote("@startuml\nA -> B\n@enduml", Path("/tmp/x.png"))
    assert img is None
    assert err and "Invalid" in err


def test_strip_include_directives():
    from app.services.plantuml_validate import sanitize_plantuml_output

    raw = "@startuml\n!include /etc/passwd\nclass Foo\n!includeurl http://evil/x\n@enduml\n"
    out = sanitize_plantuml_output(raw)
    assert "!include" not in out.lower()
    assert "class Foo" in out


def test_spec_builder_blocks_newline_include_injection():
    from app.services.plantuml_from_spec import plantuml_from_spec

    spec = {
        "diagram_type": "component",
        "components": [{"name": "Pay]\n!include /etc/passwd\n[X"}],
        "relationships": [],
    }
    out = plantuml_from_spec(spec, "component")
    assert "!include" not in out.lower()
    assert "\n!include" not in out

    flow = plantuml_from_spec(
        {
            "diagram_type": "flowchart",
            "process_steps": ["Start", "Load\n!include /tmp/evil", "Done"],
        },
        "flowchart",
    )
    assert "!include" not in flow.lower()
