"""Test suite defaults — never call live providers during unit/API tests."""

from __future__ import annotations

import os

# Must run before app.settings is imported by test modules.
os.environ["MOCK_PROVIDERS"] = "true"
os.environ.setdefault("USE_HF_INFERENCE", "false")
os.environ.setdefault("DATABASE_URL", "sqlite://")


import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
