"""Build chat/vision providers from application settings."""

from __future__ import annotations

from pathlib import Path

from uml_pipeline.llm_client import LLMClient

from app.providers.mock_provider import MockProvider
from app.settings import Settings, get_settings


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self._client = LLMClient(model=model, provider="openai", base_url=base_url, api_key=api_key)

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str):
        self.model = model
        self._client = LLMClient(model=model, provider="ollama")

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)


def build_chat_provider(settings: Settings | None = None, model: str | None = None):
    settings = settings or get_settings()
    model = model or settings.spec_model
    if settings.mock_providers:
        return MockProvider()
    if settings.use_ollama:
        return OllamaProvider(model)
    return OpenAIProvider(model, base_url=settings.openai_base_url, api_key=settings.openai_api_key)


def build_code_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    return build_chat_provider(settings, model=settings.code_model)


def build_vlm_providers(settings: Settings | None = None) -> dict[str, object]:
    """Map paper weight keys -> provider instances (or unavailable markers)."""
    settings = settings or get_settings()
    keys = list(settings.vlm_weight_map.keys())
    models = settings.vlm_model_list
    providers: dict[str, object] = {}
    for i, key in enumerate(keys):
        model = models[i] if i < len(models) else models[-1] if models else "mock-vlm"
        if settings.mock_providers:
            providers[key] = MockProvider()
        elif settings.use_ollama:
            providers[key] = OllamaProvider(model)
        else:
            providers[key] = OpenAIProvider(
                model, base_url=settings.openai_base_url, api_key=settings.openai_api_key
            )
        getattr(providers[key], "model", None)
        if not hasattr(providers[key], "model"):
            providers[key].model = model  # type: ignore[attr-defined]
        else:
            # ensure model attribute for logging
            try:
                providers[key].model = model  # type: ignore[attr-defined]
            except Exception:
                pass
    return providers
