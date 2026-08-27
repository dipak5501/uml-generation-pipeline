"""Application settings (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

# Re-export for routers/scripts
__all__ = ["Settings", "get_settings", "ROOT"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "UML Dataset Generation with Multimodal Verification"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'uml_app.db'}"
    artifact_dir: Path = ROOT / "data" / "artifacts"
    plantuml_jar: Path = ROOT / "tools" / "plantuml.jar"
    image_format: str = "png"
    max_repair_attempts: int = 3
    adaptation_memory_path: Path = ROOT / "data" / "adaptation_memory.json"
    mock_providers: bool = True

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    # Qwen2.5-VL needs a newer Ollama (0.32+) than llama3.2-vision (0.24 mllama).
    # Dual-serve: primary :11434 = 0.24 for LLaMA-Vision; :11435 = 0.32 for Qwen-VL.
    ollama_qwen_base_url: str = "http://127.0.0.1:11435"
    use_ollama: bool = False

    # Hugging Face Inference Providers (OpenAI-compatible router)
    use_hf_inference: bool = False
    hf_token: str = ""
    hf_base_url: str = "https://router.huggingface.co/v1"

    # Paper models (HF repo ids). Ollama tags are mapped automatically when USE_OLLAMA=true.
    spec_model: str = "meta-llama/Llama-3.2-1B-Instruct"
    code_model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    vlm_models: str = "qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b"
    # Aya-Vision-8B is NOT on Ollama. Backend for the 3rd VLM slot:
    #   local          = paper-exact CohereLabs/aya-vision-8b via transformers (MPS/CPU)
    #   ollama_standin = llava:7b (local demo only; not paper-exact)
    #   hf             = Hugging Face router model in AYA_VLM_MODEL
    #   openai_compat  = any OpenAI-compatible server (vLLM on GCP/local GPU)
    vlm_aya_backend: str = "local"
    aya_vlm_model: str = "CohereLabs/aya-vision-8b"
    aya_vlm_base_url: str = ""  # e.g. http://YOUR_GCP_VM:8000/v1

    # VLM weights (MMMU) from the paper
    weight_qwen25vl3b: float = 53.1
    weight_llama32vl11b: float = 50.7
    weight_aya_vision_8b: float = 39.9

    # Paper majority-vote acceptance gate
    acceptance_tau: float = 4.0
    min_composite_for_dataset: float = 3.0
    enable_cot: bool = True

    # Local LoRA fine-tuned PlantUML generator (MLX on Apple Silicon)
    use_finetuned_code: bool = False
    finetuned_base_model: str = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
    finetuned_adapter_path: Path = ROOT / "models" / "uml-plantuml-lora"
    # 512 truncates complex PlantUML; 1536 is safer for class/package diagrams.
    finetuned_max_tokens: int = 1536
    # When true, score with only the first available VLM (much faster demos).
    vlm_fast_mode: bool = False
    # Interactive Generate skips VLMs unless the client sets skip_vlm=false.
    interactive_skip_vlm: bool = False

    api_base_url: str = "http://127.0.0.1:8000"

    # Optional shared secret for public deploys. Empty = open (local demo).
    api_access_token: str = ""
    # Remote agent auth (falls back to API_ACCESS_TOKEN when empty).
    remote_agent_token: str = ""
    # Max POST /api/agent/command calls per client per minute (0 = unlimited).
    remote_agent_rate_limit: int = 12
    # Cursor SDK — enables agent-prompt remote commands when set.
    cursor_api_key: str = ""
    # Comma-separated origins, or "*" for open demos (credentials disabled when "*").
    cors_origins: str = "*"

    @property
    def vlm_weight_map(self) -> dict[str, float]:
        return {
            "qwen25vl3b": self.weight_qwen25vl3b,
            "llama32vl11b": self.weight_llama32vl11b,
            "aya_vision_8b": self.weight_aya_vision_8b,
        }

    @property
    def vlm_model_list(self) -> list[str]:
        return [m.strip() for m in self.vlm_models.split(",") if m.strip()]

    @property
    def provider_name(self) -> str:
        """Primary label for UI: prefer fine-tuned code stage when enabled."""
        if self.use_finetuned_code:
            return "finetuned-mlx"
        if self.mock_providers:
            return "mock"
        if self.use_ollama:
            return "ollama"
        if self.use_hf_inference:
            return "huggingface"
        return "openai"

    @property
    def provider_summary(self) -> str:
        """Human-readable mix of stages (spec / code / VLM)."""
        if self.mock_providers and not self.use_finetuned_code:
            return "mock"
        if self.mock_providers:
            other = "mock"
        elif self.use_ollama:
            other = "ollama"
        elif self.use_hf_inference:
            other = "huggingface"
        else:
            other = "openai"
        code = "finetuned-mlx" if self.use_finetuned_code else other
        if self.use_finetuned_code and self.mock_providers:
            return f"spec/VLM={other} · code={code}"
        if self.use_hf_inference and not self.mock_providers:
            code_label = (
                "finetuned-mlx"
                if self.use_finetuned_code
                else self.code_model.split("/")[-1]
            )
            return (
                f"HF · spec={self.spec_model.split('/')[-1]} · code={code_label}"
            )
        if self.use_finetuned_code:
            return f"spec/VLM={other} · code={code}"
        return code

@lru_cache
def get_settings() -> Settings:
    return Settings()
