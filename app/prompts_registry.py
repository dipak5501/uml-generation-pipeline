"""Versioned prompt registry backed by prompts/ files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

DIAGRAM_PROMPT_MAP = {
    "class": "tech_spec_to_class",
    "object": "tech_spec_to_object",
    "component": "tech_spec_to_component",
    "package": "tech_spec_to_package",
}

ALL_DIAGRAM_TYPES = ("class", "object", "component", "package")



@dataclass(frozen=True)
class PromptRef:
    name: str
    version: str
    path: Path
    body: str


def list_prompt_files() -> list[Path]:
    if not PROMPTS_DIR.is_dir():
        return []
    return sorted(PROMPTS_DIR.glob("*.v*.txt"))


def load_prompt(name: str, version: str = "v1") -> PromptRef:
    path = PROMPTS_DIR / f"{name}.{version}.txt"
    if not path.is_file():
        matches = list(PROMPTS_DIR.glob(f"{name}.{version}*.txt"))
        if not matches:
            raise FileNotFoundError(f"Prompt not found: {name} {version} ({path})")
        path = matches[0]
    body = path.read_text(encoding="utf-8")
    return PromptRef(name=name, version=version, path=path, body=body)


def _safe_format(template: str, **kwargs: str) -> str:
    """Replace {key} placeholders only; leave other braces untouched."""

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in kwargs:
            return str(kwargs[key])
        return match.group(0)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", repl, template)


def render_prompt(name: str, version: str = "v1", **kwargs: str) -> tuple[PromptRef, str]:
    ref = load_prompt(name, version)
    return ref, _safe_format(ref.body, **kwargs)


def diagram_prompt_name(diagram_type: str) -> str:
    if diagram_type not in DIAGRAM_PROMPT_MAP:
        raise ValueError(f"Unknown diagram type: {diagram_type}")
    return DIAGRAM_PROMPT_MAP[diagram_type]
