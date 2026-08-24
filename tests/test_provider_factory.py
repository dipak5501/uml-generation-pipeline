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


def test_use_aya_false_marks_unavailable():
    from app.providers.factory import UnavailableProvider

    settings = Settings(
        mock_providers=False,
        use_aya=False,
        vlm_aya_backend="openai_compat",
        aya_vlm_base_url="http://127.0.0.1:8001/v1",
    )
    p = _build_aya_provider(settings, "aya-vision:8b")
    assert isinstance(p, UnavailableProvider)
    with pytest.raises(RuntimeError, match="USE_AYA=false"):
        p.vision_score("/tmp/x.png", "score")


def test_detect_finetuned_backend_peft_vs_mlx(tmp_path):
    from app.providers.finetuned_provider import (
        detect_finetuned_backend,
        peft_base_model_id,
        build_finetuned_provider,
        FinetunedPeftProvider,
        FinetunedMLXProvider,
    )

    peft_dir = tmp_path / "peft"
    peft_dir.mkdir()
    (peft_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    assert detect_finetuned_backend(peft_dir, "Qwen/Qwen2.5-0.5B-Instruct") == "peft"
    provider = build_finetuned_provider("mlx-community/Qwen2.5-0.5B-Instruct-4bit", peft_dir)
    assert isinstance(provider, FinetunedPeftProvider)
    assert peft_base_model_id("mlx-community/Qwen2.5-0.5B-Instruct-4bit") == "Qwen/Qwen2.5-0.5B-Instruct"

    mlx_dir = tmp_path / "mlx"
    mlx_dir.mkdir()
    (mlx_dir / "adapters.safetensors").write_bytes(b"x")
    assert detect_finetuned_backend(mlx_dir, "mlx-community/Qwen2.5-0.5B-Instruct-4bit") == "mlx"
    mlx_provider = build_finetuned_provider(
        "mlx-community/Qwen2.5-0.5B-Instruct-4bit", mlx_dir
    )
    assert isinstance(mlx_provider, FinetunedMLXProvider)


def test_select_aya_device_mac_studio_128gb_allows_mps():
    from app.providers.aya_local_provider import select_aya_device

    assert (
        select_aya_device(cuda=False, mps=True, memory_gb=128.0, allow_inprocess=False)
        == "mps"
    )


def test_select_aya_device_24gb_mac_refuses_mps():
    from app.providers.aya_local_provider import select_aya_device

    with pytest.raises(RuntimeError, match="24"):
        select_aya_device(cuda=False, mps=True, memory_gb=24.0, allow_inprocess=False)


def test_select_aya_device_cuda_wins():
    from app.providers.aya_local_provider import select_aya_device

    assert select_aya_device(cuda=True, mps=True, memory_gb=24.0, allow_inprocess=False) == "cuda"


def test_aya_openai_compat_requires_base_url():
    settings = Settings(
        mock_providers=False,
        vlm_aya_backend="openai_compat",
        aya_vlm_base_url="",
    )
    with pytest.raises(RuntimeError, match="AYA_VLM_BASE_URL"):
        _build_aya_provider(settings, "aya-vision:8b")
