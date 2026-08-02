"""Package failure taxonomy."""

from app.services.package_failures import classify_package_failure


def test_empty_package_classified():
    cats = classify_package_failure("@startuml\n@enduml\n", "empty or incomplete")
    assert "empty_or_incomplete" in cats
    assert "missing_package_block" in cats


def test_self_dependency_classified():
    code = """
@startuml
package core {
  class A
}
core ..> core
@enduml
"""
    cats = classify_package_failure(code, "Self-referential dependency")
    assert "self_dependency" in cats


def test_unbalanced_braces():
    cats = classify_package_failure("@startuml\npackage core {\nclass A\n@enduml\n")
    assert "unbalanced_braces" in cats
