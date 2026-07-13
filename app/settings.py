"""Application settings (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "UML Generation Thesis App"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'uml_app.db'}"
    artifact_dir: Path = ROOT / "data" / "artifacts"
    plantuml_jar: Path = ROOT / "tools" / "plantuml.jar"
    image_format: str = "png"
    max_repair_attempts: int = 3
    mock_providers: bool = True

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    use_ollama: bool = False

    spec_model: str = "llama3.2:1b"
    code_model: str = "deepseek-r1:32b"
    vlm_models: str = "qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b"

    # Paper-aligned MMMU weights
    weight_qwen25vl3b: float = 53.1
    weight_llama32vl11b: float = 50.7
    weight_aya_vision_8b: float = 39.9

    api_base_url: str = "http://127.0.0.1:8000"

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
        if self.mock_providers:
            return "mock"
        if self.use_ollama:
            return "ollama"
        return "openai"


@lru_cache
def get_settings() -> Settings:
    return Settings()
