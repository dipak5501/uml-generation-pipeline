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
    assert "no class" in spec.lower() or "script" in spec.lower()
    assert "Input two numbers" in spec or "num1" in spec
    # Variables may appear under configuration, but not as invented UML classes list alone
    assert "Do NOT invent classes from variable names" in spec


def test_detect_source_language():
    assert detect_source_language(SAMPLE, "source_code") == "python"
    assert detect_source_language("Build a bookstore.", "requirement") is None


def test_procedural_script_has_no_type_entities():
    from app.services.code_analysis import analyze_source_code
    from app.services.spec_json import structure_to_spec_json

    s = analyze_source_code(PROCEDURAL)
    assert s.classes == []
    assert s.entity_names() == []
    data = structure_to_spec_json(PROCEDURAL, "class")
    assert data.get("script_without_types")
    assert data.get("diagram_type") == "class"
