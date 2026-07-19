"""Build chat/vision providers from application settings."""

from __future__ import annotations

from pathlib import Path

from uml_pipeline.llm_client import LLMClient

from app.providers.mock_provider import MockProvider
from app.settings import Settings, get_settings

# Paper / thesis models (Hugging Face IDs) → Ollama tags when USE_OLLAMA=true
_OLLAMA_MODEL_MAP = {
    "meta-llama/Llama-3.2-1B-Instruct": "llama3.2:1b",
    "meta-llama/llama-3.2-1b-instruct": "llama3.2:1b",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": "deepseek-r1:32b",
    "deepseek-ai/deepseek-r1-distill-qwen-32b": "deepseek-r1:32b",
}


def _ollama_model_id(model: str) -> str:
    if "/" not in model:
        return model
    return _OLLAMA_MODEL_MAP.get(model) or _OLLAMA_MODEL_MAP.get(model.lower()) or model.split("/")[-1].lower()


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self._client = LLMClient(model=model, provider="openai", base_url=base_url, api_key=api_key)

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)


class HuggingFaceProvider:
    """OpenAI-compatible Hugging Face Inference Providers router."""

    name = "huggingface"

    def __init__(
        self,
        model: str,
        *,
        token: str,
        base_url: str = "https://router.huggingface.co/v1",
    ):
        self.model = model
        self._client = LLMClient(
            model=model,
            provider="openai",
            base_url=base_url,
            api_key=token,
        )

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str):
        self.model = _ollama_model_id(model)
        self._client = LLMClient(model=self.model, provider="ollama")

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)


def _live_chat_provider(settings: Settings, model: str):
    """Non-mock chat provider for a given model id."""
    if settings.use_ollama:
        return OllamaProvider(model)
    if settings.use_hf_inference:
        token = settings.hf_token or settings.openai_api_key
        if not token:
            raise RuntimeError(
                "USE_HF_INFERENCE=true but HF_TOKEN is empty. "
                "Create a token at https://huggingface.co/settings/tokens "
                "with Inference Providers permission, accept the Llama license, "
                "then set HF_TOKEN in .env."
            )
        return HuggingFaceProvider(
            model,
            token=token,
            base_url=settings.hf_base_url,
        )
    return OpenAIProvider(
        model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
    )


def build_chat_provider(settings: Settings | None = None, model: str | None = None):
    settings = settings or get_settings()
    model = model or settings.spec_model
    if settings.mock_providers:
        return MockProvider()
    return _live_chat_provider(settings, model)


def build_code_provider(settings: Settings | None = None):
    """PlantUML code model — prefers local LoRA fine-tune when enabled."""
    settings = settings or get_settings()
    if settings.use_finetuned_code:
        from app.providers.finetuned_provider import FinetunedMLXProvider

        return FinetunedMLXProvider(
            base_model=settings.finetuned_base_model,
            adapter_path=settings.finetuned_adapter_path,
            max_tokens=settings.finetuned_max_tokens,
            temperature=0.2,
        )
    return build_chat_provider(settings, model=settings.code_model)


def build_base_code_provider(settings: Settings | None = None):
    """Non-fine-tuned code provider for safe fallback retries."""
    settings = settings or get_settings()
    if settings.mock_providers:
        return MockProvider()
    return _live_chat_provider(settings, settings.code_model)


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
        else:
            providers[key] = _live_chat_provider(settings, model)
        try:
            providers[key].model = model  # type: ignore[attr-defined]
        except Exception:
            pass
    return providers
