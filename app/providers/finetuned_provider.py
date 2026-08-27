"""Local MLX LoRA fine-tuned PlantUML code provider."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, tuple[object, object]] = {}


def _load(model_id: str, adapter_path: Path):
    key = f"{model_id}::{adapter_path.resolve()}"
    with _lock:
        if key in _cache:
            return _cache[key]
        from mlx_lm import load

        logger.info("Loading fine-tuned MLX model %s + adapters %s", model_id, adapter_path)
        model, tokenizer = load(model_id, adapter_path=str(adapter_path))
        _cache[key] = (model, tokenizer)
        return model, tokenizer


class FinetunedMLXProvider:
    """Chat provider backed by an MLX LoRA adapter trained on open UML/PlantUML corpora."""

    name = "finetuned-mlx"

    def __init__(
        self,
        base_model: str,
        adapter_path: Path,
        *,
        max_tokens: int = 1536,
        temperature: float = 0.2,
    ):
        self.base_model = base_model
        self.adapter_path = Path(adapter_path)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = f"finetuned:{self.adapter_path.name}"

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        adapters = self.adapter_path / "adapters.safetensors"
        if not self.adapter_path.exists() or not adapters.is_file():
            raise FileNotFoundError(
                f"Fine-tuned adapter weights missing at {adapters}. "
                "Run: bash scripts/run_finetune_openmpi.sh"
            )
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        model, tokenizer = _load(self.base_model, self.adapter_path)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if hasattr(tokenizer, "apply_chat_template"):
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            prompt = f"System: {system}\n\nUser: {user}\n\nAssistant:"

        temp = temperature if temperature is not None else self.temperature
        sampler = make_sampler(temp=max(0.01, float(temp)))
        text = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=self.max_tokens,
            sampler=sampler,
            verbose=False,
        )
        return (text or "").strip()

    def vision_score(self, image_path: Path, prompt: str) -> int:
        raise NotImplementedError("Fine-tuned provider is text-only (PlantUML code model)")

    def vision_assess(self, image_path: Path, prompt: str):
        raise NotImplementedError("Fine-tuned provider is text-only (PlantUML code model)")
