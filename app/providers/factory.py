"""Build chat/vision providers from application settings."""

from __future__ import annotations

from pathlib import Path

from uml_pipeline.llm_client import LLMClient, VisionAssessment

from app.providers.mock_provider import MockProvider
from app.settings import Settings, get_settings

# Paper / thesis models (Hugging Face IDs) → Ollama tags when USE_OLLAMA=true
_OLLAMA_MODEL_MAP = {
    "meta-llama/Llama-3.2-1B-Instruct": "llama3.2:1b",
    "meta-llama/llama-3.2-1b-instruct": "llama3.2:1b",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": "deepseek-r1:32b",
    "deepseek-ai/deepseek-r1-distill-qwen-32b": "deepseek-r1:32b",
}

# Ollama-style VLM tags → Hugging Face vision model IDs
_HF_VLM_MAP = {
    "qwen2.5vl:3b": "Qwen/Qwen2.5-VL-3B-Instruct",
    "qwen2.5-vl:3b": "Qwen/Qwen2.5-VL-3B-Instruct",
    "llama3.2-vision:11b": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "llama3.2-vision": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "aya-vision:8b": "CohereLabs/aya-vision-8b",
    "aya-vision": "CohereLabs/aya-vision-8b",
}

# Paper Aya-Vision is not published on Ollama; map to a local vision stand-in.
_OLLAMA_VLM_FALLBACKS = {
    "aya-vision:8b": "llava:7b",
    "aya-vision": "llava:7b",
}


def _ollama_model_id(model: str) -> str:
    if "/" not in model:
        return model
    return _OLLAMA_MODEL_MAP.get(model) or _OLLAMA_MODEL_MAP.get(model.lower()) or model.split("/")[-1].lower()


def _resolve_model_for_provider(settings: Settings, model: str) -> str:
    """Map Ollama tags ↔ HF repo ids depending on the active backend."""
    if settings.use_ollama:
        return _ollama_model_id(model)
    if settings.use_hf_inference:
        mapped = _HF_VLM_MAP.get(model) or _HF_VLM_MAP.get(model.lower())
        if mapped:
            return mapped
    return model


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self._client = LLMClient(model=model, provider="openai", base_url=base_url, api_key=api_key)

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        return self._client.vision_assess(image_path, prompt)


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

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        return self._client.vision_assess(image_path, prompt)


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, *, ollama_url: str | None = None, label: str | None = None):
        run_tag = _ollama_model_id(model)
        self.model = label or run_tag
        self._client = LLMClient(model=run_tag, provider="ollama", ollama_url=ollama_url)

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        return self._client.chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self._client.vision_score(image_path, prompt)

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        return self._client.vision_assess(image_path, prompt)


def _ollama_url_for_model(settings: Settings, model: str) -> str:
    """Route Qwen2.5-VL to the newer Ollama host; everything else to primary."""
    tag = _ollama_model_id(model).lower()
    if tag.startswith("qwen2.5vl") or tag.startswith("qwen2.5-vl"):
        return (settings.ollama_qwen_base_url or settings.ollama_base_url).rstrip("/")
    return settings.ollama_base_url.rstrip("/")


def _resolve_ollama_vlm_tag(model: str) -> tuple[str, str]:
    """Return (run_tag, display_name). Aya falls back to llava locally."""
    raw = model.strip()
    mapped = _OLLAMA_VLM_FALLBACKS.get(raw) or _OLLAMA_VLM_FALLBACKS.get(raw.lower())
    if mapped:
        return mapped, f"{mapped} [{raw} stand-in]"
    return raw, raw


def _live_chat_provider(settings: Settings, model: str):
    """Non-mock chat provider for a given model id."""
    model = _resolve_model_for_provider(settings, model)
    if settings.use_ollama:
        run_tag, label = _resolve_ollama_vlm_tag(model)
        return OllamaProvider(
            run_tag,
            ollama_url=_ollama_url_for_model(settings, run_tag),
            label=label,
        )
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
    # DeepSeek-32B is rarely installed locally; fall back to the spec Ollama model.
    model = settings.code_model
    if settings.use_ollama:
        mapped = _ollama_model_id(model)
        if "deepseek" in mapped.lower() and "32b" in mapped.lower():
            model = settings.spec_model
    return _live_chat_provider(settings, model)


def _build_aya_provider(settings: Settings, configured_model: str) -> object:
    """Paper 3rd VLM: real Aya when possible; otherwise explicit stand-in."""
    backend = (settings.vlm_aya_backend or "ollama_standin").strip().lower()
    model_id = (settings.aya_vlm_model or "CohereLabs/aya-vision-8b").strip()

    if backend in {"local", "transformers", "mps", "local_transformers"}:
        from app.providers.aya_local_provider import LocalAyaVisionProvider

        token = settings.hf_token or settings.openai_api_key or None
        return LocalAyaVisionProvider(model_id, hf_token=token)

    if backend in {"hf", "huggingface"}:
        token = settings.hf_token or settings.openai_api_key
        if not token:
            raise RuntimeError(
                "VLM_AYA_BACKEND=hf requires HF_TOKEN. "
                "Note: CohereLabs/aya-vision-8b may be unavailable on HF Inference Providers."
            )
        return HuggingFaceProvider(
            model_id,
            token=token,
            base_url=settings.hf_base_url,
        )

    if backend in {"openai_compat", "vllm", "openai", "custom"}:
        base = (settings.aya_vlm_base_url or "").strip().rstrip("/")
        if not base:
            raise RuntimeError(
                "VLM_AYA_BACKEND=openai_compat requires AYA_VLM_BASE_URL "
                "(OpenAI-compatible vLLM endpoint serving Aya-Vision-8B)."
            )
        token = settings.hf_token or settings.openai_api_key or "EMPTY"
        return OpenAIProvider(model=model_id, base_url=base, api_key=token)

    # Default / ollama_standin: local llava mapped from aya-vision:8b
    run_tag, label = _resolve_ollama_vlm_tag(configured_model or "aya-vision:8b")
    return OllamaProvider(
        run_tag,
        ollama_url=settings.ollama_base_url.rstrip("/"),
        label=label,
    )


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
            try:
                providers[key].model = model  # type: ignore[attr-defined]
            except Exception:
                pass
            continue

        # Paper routing:
        #   qwen25vl3b     -> Ollama :11435 (qwen2.5vl:3b)
        #   llama32vl11b   -> Ollama :11434 (llama3.2-vision:11b)
        #   aya_vision_8b  -> configured Aya backend (not available on Ollama)
        if key == "aya_vision_8b":
            providers[key] = _build_aya_provider(settings, model)
        else:
            providers[key] = _live_chat_provider(settings, model)
    return providers
