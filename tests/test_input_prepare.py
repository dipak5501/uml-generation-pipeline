"""Long-input clipping and Stage-1 routing for reliability."""

from app.services.input_prepare import (
    LLM_REQUIREMENT_CHARS,
    clip_for_llm,
    is_long_input,
)
from app.services.orchestration import generate_technical_spec
from app.settings import Settings


def test_clip_keeps_head_and_tail():
    text = "HEAD_" + ("x" * 5000) + "_TAIL_Marker"
    clipped = clip_for_llm(text, 1000)
    assert len(clipped) <= 1100
    assert clipped.startswith("HEAD_")
    assert "TAIL_Marker" in clipped
    assert "truncated" in clipped.lower()


def test_short_text_unchanged():
    assert clip_for_llm("hello", LLM_REQUIREMENT_CHARS) == "hello"


def test_is_long_input():
    assert not is_long_input("short")
    assert is_long_input("a" * 4000)


def test_long_source_code_uses_structure(monkeypatch):
    code = (
        "class Alpha:\n    def run(self): pass\n\n"
        + ("# filler\n" * 800)
        + "class Omega:\n    def stop(self): pass\n"
    )
    assert is_long_input(code)
    settings = Settings(mock_providers=True)
    prose, spec_json, *_rest = generate_technical_spec(
        code, "class", settings=settings, input_mode="source_code"
    )
    names = {e["name"] for e in spec_json.get("entities") or []}
    assert "Alpha" in names
    assert "Omega" in names
    assert "Entities" in prose or "Alpha" in prose
