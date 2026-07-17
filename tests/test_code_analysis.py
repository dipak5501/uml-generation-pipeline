"""Tests for source-code structure extraction."""

from app.services.code_analysis import (
    analyze_source_code,
    detect_source_language,
    looks_like_source_code,
    resolve_input_mode,
    structure_to_spec,
)


SAMPLE = '''
class User:
    def authenticate(self, password: str) -> bool:
        return True

class Order(User):
    def total(self) -> float:
        return 0.0
'''


def test_looks_like_source_code():
    assert looks_like_source_code(SAMPLE)
    assert not looks_like_source_code("Build a bookstore with carts and checkout.")


def test_analyze_python_classes():
    s = analyze_source_code(SAMPLE)
    assert "User" in s.classes
    assert "Order" in s.classes
    assert "User" in s.bases.get("Order", [])


def test_structure_to_spec_mentions_classes():
    spec = structure_to_spec(SAMPLE, "class")
    assert "User" in spec
    assert "Order" in spec
    assert "Technical Specification" in spec


def test_resolve_input_mode_auto_detects_code():
    assert resolve_input_mode(SAMPLE, "requirement") == "source_code"
    assert resolve_input_mode("Build a bookstore.", "requirement") == "requirement"


def test_detect_source_language():
    assert detect_source_language(SAMPLE, "source_code") == "python"
    assert detect_source_language("Build a bookstore.", "requirement") is None
