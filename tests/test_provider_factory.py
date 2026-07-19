"""Provider factory helpers."""

from app.providers.factory import _ollama_model_id


def test_ollama_maps_hf_llama_and_deepseek():
    assert _ollama_model_id("meta-llama/Llama-3.2-1B-Instruct") == "llama3.2:1b"
    assert _ollama_model_id("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B") == "deepseek-r1:32b"
    assert _ollama_model_id("llama3.2:1b") == "llama3.2:1b"
