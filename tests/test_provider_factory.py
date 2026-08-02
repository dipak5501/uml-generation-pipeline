"""Provider factory helpers."""

from app.providers.factory import _ollama_model_id, _resolve_model_for_provider
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
