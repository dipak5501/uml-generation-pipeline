"""Provider factory helpers."""

import pytest

from app.providers.factory import (
    OpenAIProvider,
    OllamaProvider,
    _build_aya_provider,
    _ollama_model_id,
    _resolve_model_for_provider,
    build_vlm_providers,
)
from app.settings import Settings


def test_ollama_maps_hf_llama_and_deepseek():
    assert _ollama_model_id("meta-llama/Llama-3.2-1B-Instruct") == "llama3.2:1b"
    assert _ollama_model_id("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B") == "deepseek-r1:32b"
    assert _ollama_model_id("llama3.2:1b") == "llama3.2:1b"


def test_hf_maps_ollama_vlm_tags():
    settings = Settings(mock_providers=False, use_hf_inference=True, use_ollama=False, hf_token="x")
    assert (
        _resolve_model_for_provider(settings, "qwen2.5vl:3b")
        == "Qwen/Qwen2.5-VL-3B-Instruct"
    )
    assert (
        _resolve_model_for_provider(settings, "llama3.2-vision:11b")
        == "meta-llama/Llama-3.2-11B-Vision-Instruct"
    )
    assert (
        _resolve_model_for_provider(settings, "aya-vision:8b")
        == "CohereLabs/aya-vision-8b"
    )


def test_aya_openai_compat_backend():
    settings = Settings(
        mock_providers=False,
        use_ollama=True,
        vlm_aya_backend="openai_compat",
        aya_vlm_model="CohereLabs/aya-vision-8b",
        aya_vlm_base_url="http://127.0.0.1:9000/v1",
        hf_token="x",
    )
    p = _build_aya_provider(settings, "aya-vision:8b")
    assert isinstance(p, OpenAIProvider)
    assert p.model == "CohereLabs/aya-vision-8b"


def test_aya_standin_is_ollama_llava():
    settings = Settings(
        mock_providers=False,
        use_ollama=True,
        vlm_aya_backend="ollama_standin",
        ollama_base_url="http://127.0.0.1:11434",
    )
    p = _build_aya_provider(settings, "aya-vision:8b")
    assert isinstance(p, OllamaProvider)
    assert "llava" in str(p.model).lower()


def test_aya_local_backend():
    from app.providers.aya_local_provider import LocalAyaVisionProvider

    settings = Settings(
        mock_providers=False,
        use_ollama=True,
        vlm_aya_backend="local",
        aya_vlm_model="CohereLabs/aya-vision-8b",
        hf_token="x",
    )
    p = _build_aya_provider(settings, "aya-vision:8b")
    assert isinstance(p, LocalAyaVisionProvider)
    assert p.model == "CohereLabs/aya-vision-8b"


def test_build_vlm_providers_hybrid_keys():
    settings = Settings(
        mock_providers=False,
        use_ollama=True,
        use_hf_inference=False,
        vlm_models="qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b",
        vlm_aya_backend="openai_compat",
        aya_vlm_base_url="http://127.0.0.1:9000/v1",
        aya_vlm_model="CohereLabs/aya-vision-8b",
        hf_token="x",
    )
    providers = build_vlm_providers(settings)
    assert set(providers) == {"qwen25vl3b", "llama32vl11b", "aya_vision_8b"}
    assert isinstance(providers["aya_vision_8b"], OpenAIProvider)


def test_aya_openai_compat_requires_base_url():
    settings = Settings(
        mock_providers=False,
        vlm_aya_backend="openai_compat",
        aya_vlm_base_url="",
    )
    with pytest.raises(RuntimeError, match="AYA_VLM_BASE_URL"):
        _build_aya_provider(settings, "aya-vision:8b")
