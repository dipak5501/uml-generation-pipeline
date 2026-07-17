"""Utilities for Chain-of-Thought PlantUML generation (paper Stage 2)."""

from __future__ import annotations

import re

from app.services.scoring import strip_private_reasoning
from uml_pipeline.render import extract_plantuml_block


COT_SYSTEM = (
    "You are a UML expert. Use Chain-of-Thought inside <think>...</think> tags first: "
    "decompose entities, choose UML connectors, validate hierarchy. "
    "Then output ONLY final PlantUML between @startuml and @enduml. "
    "Never reveal private reasoning outside <think> tags."
)


def finalize_plantuml_output(raw: str) -> str:
    """Strip CoT / fences and normalize to a single PlantUML block."""
    cleaned = strip_private_reasoning(raw)
    return extract_plantuml_block(cleaned)


def has_cot_block(raw: str) -> bool:
    return bool(re.search(r"<think>.*?</think>", raw, flags=re.I | re.S))
