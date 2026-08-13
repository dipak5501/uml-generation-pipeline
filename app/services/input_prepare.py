"""Prepare long requirements/code for small local LLMs without losing grounding."""

from __future__ import annotations

# Soft caps for what we send to tiny Stage-1 / LoRA models.
# Full text is still used for entity grounding in ensure_valid_spec / code analysis.
LLM_REQUIREMENT_CHARS = 4_500
LLM_SOURCE_CODE_CHARS = 6_000
LORA_SPEC_CHARS = 2_800
LONG_INPUT_CHARS = 3_000


def clip_for_llm(text: str, limit: int) -> str:
    """Keep head + tail so class names at the end of files are not lost."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = int(limit * 0.72)
    tail = limit - head - 80
    if tail < 200:
        return text[: limit - 40].rstrip() + "\n...[truncated for model length]..."
    return (
        text[:head].rstrip()
        + "\n\n...[middle truncated for model length; full text still used for grounding]...\n\n"
        + text[-tail:].lstrip()
    )


def is_long_input(text: str) -> bool:
    return len(text or "") >= LONG_INPUT_CHARS
