"""Provider protocol for chat and vision scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from uml_pipeline.llm_client import VisionAssessment


@runtime_checkable
class ModelProvider(Protocol):
    name: str

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        ...

    def vision_score(self, image_path: Path, prompt: str) -> int:
        ...

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        ...
