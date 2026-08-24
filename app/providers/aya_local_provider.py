"""Local paper-exact Aya-Vision-8B scorer (Apple MPS / CPU)."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from uml_pipeline.llm_client import VisionAssessment, _score_from_vlm_text

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_MODEL = None
_PROCESSOR = None
_MODEL_ID: str | None = None


def _load(model_id: str, hf_token: str | None = None):
    global _MODEL, _PROCESSOR, _MODEL_ID
    if _MODEL is not None and _MODEL_ID == model_id:
        return _MODEL, _PROCESSOR

    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    local_dir = Path(model_id)
    is_local = local_dir.is_dir()
    source = str(local_dir.resolve()) if is_local else model_id
    logger.info("Loading Aya-Vision from %s …", source)

    allow_inprocess = os.getenv("UML_ALLOW_AYA_INPROCESS", "").lower() in {"1", "true", "yes"}
    if torch.cuda.is_available():
        device = "cuda"
        dtype = torch.float16
    elif allow_inprocess and torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float16
    elif allow_inprocess:
        device = "cpu"
        dtype = torch.float32
    else:
        raise RuntimeError(
            "Refusing to load Aya-Vision-8B in-process on CPU/MPS (known hang / timeout). "
            "Serve it with vLLM on a CUDA GPU and set VLM_AYA_BACKEND=openai_compat "
            "AYA_VLM_BASE_URL=http://127.0.0.1:8001/v1. Override only with "
            "UML_ALLOW_AYA_INPROCESS=true for debugging."
        )
    token = None if is_local else (hf_token or True)

    processor = AutoProcessor.from_pretrained(
        source,
        trust_remote_code=True,
        token=token,
        local_files_only=is_local,
    )
    model = AutoModelForImageTextToText.from_pretrained(
        source,
        trust_remote_code=True,
        torch_dtype=dtype,
        token=token,
        local_files_only=is_local,
        low_cpu_mem_usage=True,
    )
    model = model.to(device)
    model.eval()
    _MODEL, _PROCESSOR, _MODEL_ID = model, processor, model_id
    logger.info("Aya-Vision ready on %s", device)
    return _MODEL, _PROCESSOR


def unload_aya_model() -> None:
    global _MODEL, _PROCESSOR, _MODEL_ID
    with _LOCK:
        _MODEL = None
        _PROCESSOR = None
        _MODEL_ID = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass


class LocalAyaVisionProvider:
    """Paper Aya-Vision-8B via local transformers (not Ollama stand-in)."""

    name = "aya-local"

    def __init__(self, model_id: str = "CohereLabs/aya-vision-8b", *, hf_token: str | None = None):
        self.model_id = model_id
        self.model = f"aya-vision-8b (local)" if Path(model_id).is_dir() else model_id
        self.hf_token = hf_token

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        raise NotImplementedError("Local Aya provider is vision-only for VLM scoring")

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self.vision_assess(image_path, prompt).score

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        from PIL import Image
        import torch

        with _LOCK:
            model, processor = _load(self.model_id, self.hf_token)
            device = next(model.parameters()).device
            image = Image.open(image_path).convert("RGB")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            inputs = processor.apply_chat_template(
                messages,
                padding=True,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
            prompt_len = int(inputs["input_ids"].shape[-1])
            with torch.inference_mode():
                out = model.generate(**inputs, max_new_tokens=128, do_sample=False)
            text = processor.tokenizer.decode(
                out[0][prompt_len:], skip_special_tokens=True
            ).strip()
            if not text:
                text = processor.tokenizer.decode(out[0], skip_special_tokens=True).strip()

        score, explanation = _score_from_vlm_text(text)
        return VisionAssessment(score=score, explanation=explanation, raw_output=text)
