"""Local LoRA fine-tuned PlantUML code providers (MLX on Apple, PEFT on CUDA)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_mlx_lock = threading.Lock()
_mlx_cache: dict[str, tuple[object, object]] = {}
_peft_lock = threading.Lock()
_peft_cache: dict[str, tuple[object, object]] = {}


def peft_base_model_id(model_id: str) -> str:
    """Map Apple MLX 4-bit ids to the Hugging Face base used for CUDA PEFT."""
    mid = (model_id or "").strip()
    lowered = mid.lower().replace("_", "-")
    if "qwen2.5-0.5b" in lowered or mid.startswith("mlx-community/"):
        return "Qwen/Qwen2.5-0.5B-Instruct"
    return mid or "Qwen/Qwen2.5-0.5B-Instruct"


def detect_finetuned_backend(adapter_path: Path, base_model: str = "") -> str:
    """Return ``peft`` (NVIDIA/HF) or ``mlx`` (Apple Silicon) from adapter files."""
    path = Path(adapter_path)
    if (path / "adapter_config.json").is_file():
        return "peft"
    if (path / "adapter_model.safetensors").is_file() or (path / "adapter_model.bin").is_file():
        return "peft"
    mlx_adapter = path / "adapters.safetensors"
    if mlx_adapter.is_file() or list(path.glob("*_adapters.safetensors")):
        return "mlx"
    if "mlx-community" in (base_model or "").lower():
        return "mlx"
    return "peft"


def build_finetuned_provider(
    base_model: str,
    adapter_path: Path,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.2,
):
    backend = detect_finetuned_backend(adapter_path, base_model)
    if backend == "peft":
        return FinetunedPeftProvider(
            base_model=peft_base_model_id(base_model),
            adapter_path=adapter_path,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    return FinetunedMLXProvider(
        base_model=base_model,
        adapter_path=adapter_path,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _load_mlx(model_id: str, adapter_path: Path):
    key = f"{model_id}::{adapter_path.resolve()}"
    with _mlx_lock:
        if key in _mlx_cache:
            return _mlx_cache[key]
        from mlx_lm import load

        logger.info("Loading fine-tuned MLX model %s + adapters %s", model_id, adapter_path)
        model, tokenizer = load(model_id, adapter_path=str(adapter_path))
        _mlx_cache[key] = (model, tokenizer)
        return model, tokenizer


def _load_peft(model_id: str, adapter_path: Path):
    key = f"{model_id}::{adapter_path.resolve()}"
    with _peft_lock:
        if key in _peft_cache:
            return _peft_cache[key]
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA PEFT PlantUML adapter requires an NVIDIA GPU. "
                "On Apple Silicon train/load MLX adapters instead "
                "(scripts/finetune_plantuml.py). Do not set USE_FINETUNED_CODE=true "
                "with Apple MLX files on Linux."
            )
        logger.info("Loading PEFT LoRA %s + adapters %s", model_id, adapter_path)
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        dtype = torch.float16
        base = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="cuda",
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, str(adapter_path))
        model.eval()
        _peft_cache[key] = (model, tokenizer)
        return model, tokenizer


class FinetunedMLXProvider:
    """Chat provider backed by an MLX LoRA adapter trained on the 8k UML corpus."""

    name = "finetuned-mlx"

    def __init__(
        self,
        base_model: str,
        adapter_path: Path,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ):
        self.base_model = base_model
        self.adapter_path = Path(adapter_path)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = f"finetuned:{self.adapter_path.name}"

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        if not self.adapter_path.exists():
            raise FileNotFoundError(
                f"Fine-tuned adapter not found at {self.adapter_path}. "
                "Run: python scripts/finetune_plantuml.py"
            )
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        model, tokenizer = _load_mlx(self.base_model, self.adapter_path)
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


class FinetunedPeftProvider:
    """Chat provider backed by a Hugging Face PEFT LoRA adapter (NVIDIA CUDA)."""

    name = "finetuned-peft"

    def __init__(
        self,
        base_model: str,
        adapter_path: Path,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.2,
    ):
        self.base_model = peft_base_model_id(base_model)
        self.adapter_path = Path(adapter_path)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = f"finetuned-peft:{self.adapter_path.name}"

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        if not self.adapter_path.exists():
            raise FileNotFoundError(
                f"Fine-tuned PEFT adapter not found at {self.adapter_path}. "
                "Run: python scripts/finetune_plantuml_cuda.py"
            )
        import torch

        model, tokenizer = _load_peft(self.base_model, self.adapter_path)
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
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        temp = temperature if temperature is not None else self.temperature
        gen_kwargs = {
            "max_new_tokens": self.max_tokens,
            "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        }
        if temp and temp > 0.05:
            gen_kwargs.update({"do_sample": True, "temperature": float(temp)})
        else:
            gen_kwargs["do_sample"] = False
        with torch.inference_mode():
            out = model.generate(**inputs, **gen_kwargs)
        prompt_len = int(inputs["input_ids"].shape[-1])
        text = tokenizer.decode(out[0][prompt_len:], skip_special_tokens=True)
        return (text or "").strip()

    def vision_score(self, image_path: Path, prompt: str) -> int:
        raise NotImplementedError("Fine-tuned provider is text-only (PlantUML code model)")

    def vision_assess(self, image_path: Path, prompt: str):
        raise NotImplementedError("Fine-tuned provider is text-only (PlantUML code model)")
