"""Shared LoRA user-prompt formatting for training and inference."""

from __future__ import annotations

from app.services.input_prepare import LORA_SPEC_CHARS, clip_for_llm


def format_plantuml_user_prompt(
    *,
    diagram_type: str,
    specification: str,
    input_mode: str = "requirement",
    source_text: str = "",
    source_language: str | None = None,
    max_spec_chars: int = LORA_SPEC_CHARS,
) -> str:
    """Mirror ``prepare_finetune_data.row_to_messages`` user content for LoRA inference."""
    dtype = (diagram_type or "class").strip().lower()
    spec = clip_for_llm((specification or "").strip(), max_spec_chars)
    mode = (input_mode or "requirement").strip().lower()
    src = (source_text or "").strip()
    lang_label = (source_language or "").strip() or "source"

    if mode == "source_code" and src and len(src) >= 20:
        src_clip = clip_for_llm(src, max(400, max_spec_chars // 2))
        return (
            f"Target diagram type: {dtype}\n\n"
            f"Source code context ({lang_label}):\n{src_clip}\n\n"
            f"Technical specification:\n{spec}\n\n"
            f"Generate black-and-white PlantUML for a {dtype} diagram from this codebase."
        )

    return (
        f"Target diagram type: {dtype}\n\n"
        f"Technical specification:\n{spec}\n\n"
        f"Generate PlantUML for a {dtype} diagram."
    )
