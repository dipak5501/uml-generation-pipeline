"""Local paper-exact Aya-Vision-8B scorer (Apple MPS / CUDA)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from uml_pipeline.llm_client import VisionAssessment, _score_from_vlm_text

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_MODEL = None
_PROCESSOR = None
_MODEL_ID: str | None = None

# 24 GB M2 hung on model.to("mps"). Mac Studio M1 Ultra 128 GB unified memory is enough.
_AYA_MPS_MIN_GB = 64.0


def host_memory_gb() -> float:
    """Best-effort physical RAM in GiB (unified memory on Apple Silicon)."""
    if sys.platform == "darwin":
        try:
            raw = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(raw) / (1024**3)
        except (OSError, ValueError):
            return 0.0
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024**2)
        except (OSError, ValueError, IndexError):
            return 0.0
    return 0.0


def select_aya_device(
    *,
    cuda: bool,
    mps: bool,
    memory_gb: float,
    allow_inprocess: bool,
) -> str:
    """Pick cuda / mps / cpu, or raise if in-process Aya would hang on a small Mac."""
    if cuda:
        return "cuda"
    high_mem_mps = mps and memory_gb >= _AYA_MPS_MIN_GB
    if mps and (allow_inprocess or high_mem_mps):
        return "mps"
    if allow_inprocess:
        return "cpu"
    raise RuntimeError(
        "Refusing to load Aya-Vision-8B in-process on this machine "
        f"(RAM={memory_gb:.0f} GB; MPS needs ≥{_AYA_MPS_MIN_GB:.0f} GB unified memory, "
        "e.g. Mac Studio M1 Ultra 128 GB). On 24 GB Macs this hung. "
        "NVIDIA: vLLM + VLM_AYA_BACKEND=openai_compat AYA_VLM_BASE_URL=http://127.0.0.1:8001/v1. "
        "Override with UML_ALLOW_AYA_INPROCESS=true only for debugging."
    )


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
    device = select_aya_device(
        cuda=torch.cuda.is_available(),
        mps=bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()),
        memory_gb=host_memory_gb(),
        allow_inprocess=allow_inprocess,
    )
    dtype = torch.float32 if device == "cpu" else torch.float16
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
