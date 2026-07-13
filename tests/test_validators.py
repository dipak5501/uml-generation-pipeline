"""Tests for PlantUML validators and package guards."""

from app.services.plantuml_validate import (
    ensure_plantuml_bounds,
    validate_diagram,
    validate_package_semantics,
)


def test_ensure_bounds_wraps_bare_code():
    code = ensure_plantuml_bounds("class Foo")
    assert "@startuml" in code.lower()
    assert "@enduml" in code.lower()


def test_package_self_dependency_flagged():
    code = """
@startuml
package core {
  class A
}
core ..> core
@enduml
"""
    result = validate_package_semantics(code)
    assert not result.ok
    assert any("Self-referential" in m for m in result.messages)


def test_valid_nested_package_passes():
    code = """
@startuml
package core {
  package domain {
    class Entity
  }
}
package api {
  class Controller
}
api ..> core : uses
@enduml
"""
    result = validate_diagram(code, "package")
    assert result.ok


def test_unbalanced_braces_fail():
    code = "@startuml\npackage core {\nclass A\n@enduml"
    result = validate_diagram(code, "package")
    assert not result.ok
