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


PROCEDURAL = '''# Input two numbers
num1 = int(input("Enter first number: "))
num2 = int(input("Enter second number: "))
# Add them
sum = num1 + num2
# Print result
print("Sum is:", sum)
'''


def test_detect_procedural_python():
    assert detect_source_language(PROCEDURAL, "source_code") == "python"
    assert looks_like_source_code(PROCEDURAL)


def test_analyze_procedural_python_variables_and_steps():
    s = analyze_source_code(PROCEDURAL)
    assert s.language == "python"
    assert "num1" in s.variables
    assert "num2" in s.variables
    assert any("Add them" in step for step in s.steps)


def test_structure_to_spec_for_procedural_script():
    spec = structure_to_spec(PROCEDURAL, "class")
    assert "python" in spec.lower()
    assert "num1" in spec or "Input two numbers" in spec


def test_detect_source_language():
    assert detect_source_language(SAMPLE, "source_code") == "python"
    assert detect_source_language("Build a bookstore.", "requirement") is None


def test_mock_entities_from_source_spec_not_detected_header():
    from app.providers.mock_provider import _entities_from_text
    from app.services.code_analysis import structure_to_spec

    spec = structure_to_spec(PROCEDURAL, "class")
    ents = _entities_from_text(f"Technical specification:\n{spec}")
    assert "Detected" not in ents
    assert "Language" not in ents
    assert any(e.lower() in {"num1", "num2", "sum"} for e in ents)
