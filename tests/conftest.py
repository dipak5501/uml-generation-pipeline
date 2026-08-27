"""Test suite defaults — never call live providers during unit/API tests."""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Must run before app.settings is imported by test modules.
os.environ["MOCK_PROVIDERS"] = "true"
os.environ.setdefault("USE_HF_INFERENCE", "false")
os.environ.setdefault("USE_FINETUNED_CODE", "false")
os.environ.setdefault("DATABASE_URL", "sqlite://")
# Keep tests auth-free unless a fixture explicitly sets a token (avoids .env bleed).
os.environ["API_ACCESS_TOKEN"] = ""

# Prefer bundled JDK so golden acceptance tests can compile/render PlantUML in CI.
if not os.environ.get("JAVA_HOME"):
    for jdk_home in sorted(_ROOT.glob("tools/jdk-*/Contents/Home")):
        if (jdk_home / "bin" / "java").is_file():
            os.environ["JAVA_HOME"] = str(jdk_home)
            break


import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    """Reset settings cache each test; default open auth unless a fixture overrides."""
    monkeypatch.setenv("API_ACCESS_TOKEN", os.environ.get("API_ACCESS_TOKEN", ""))
    from app.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
