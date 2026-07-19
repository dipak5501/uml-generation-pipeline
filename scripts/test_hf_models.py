#!/usr/bin/env python3
"""Smoke-test Hugging Face Inference Providers for UML-Pipeline paper models."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    token = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or ""
    if not token:
        print("Set HF_TOKEN in .env first (https://huggingface.co/settings/tokens).")
        return 1

    base = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1").rstrip("/")
    spec = os.getenv("SPEC_MODEL", "meta-llama/Llama-3.2-1B-Instruct")
    code = os.getenv("CODE_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")

    from app.providers.factory import HuggingFaceProvider

    print(f"Router: {base}")
    print(f"Spec model: {spec}")
    print(f"Code model: {code}")
    print()

    for label, model in (("SPEC", spec), ("CODE", code)):
        print(f"--- {label}: {model} ---")
        try:
            p = HuggingFaceProvider(model, token=token, base_url=base)
            out = p.chat(
                "You are a concise assistant.",
                "Reply with exactly: OK",
                temperature=0.1,
            )
            print("OK →", (out or "")[:200].replace("\n", " "))
        except Exception as exc:
            print("FAIL →", type(exc).__name__, str(exc)[:400])
            if "Llama" in model or "meta-llama" in model:
                print(
                    "  Hint: accept the model license at "
                    "https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct"
                )
            if "DeepSeek" in model or "32B" in model:
                print(
                    "  Hint: 32B may need HF credits / a paid Inference Provider. "
                    "Try again later or use Ollama locally for code stage."
                )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
