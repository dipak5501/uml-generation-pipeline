"""Tests for PlantUML validators and package guards."""

from app.services.plantuml_validate import (
    ensure_plantuml_bounds,
    normalize_plantuml_relations,
    sanitize_plantuml_output,
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


def test_empty_package_fails():
    code = "@startuml\nand @enduml\n@enduml"
    result = validate_diagram(code, "package")
    assert not result.ok


def test_empty_class_diagram_fails():
    result = validate_diagram("@startuml\n@enduml\n", "class")
    assert not result.ok
    assert any("empty" in m.lower() for m in result.messages)


def test_bare_package_line_fails():
    result = validate_diagram("@startuml\npackage Banking;\n@enduml\n", "package")
    assert not result.ok
    assert any("package Name" in m or "bare" in m.lower() for m in result.messages)


def test_worded_inheritance_arrow_normalized():
    broken = """@startuml
class Model;
class DomainObject {
  id: int32;
  name: string;
  save(): void;
}
Model --inheritance--> DomainObject;
@enduml
"""
    fixed = sanitize_plantuml_output(broken)
    assert "--inheritance-->" not in fixed
    assert "Model --|> DomainObject" in fixed
    assert "class Model;" not in fixed
    assert "id: int32;" not in fixed
    assert validate_diagram(fixed, "class").ok


def test_normalize_relations_helper():
    line = normalize_plantuml_relations("A --composition--> B;")
    assert "A *-- B" in line


def test_flowchart_rejects_class_diagram():
    code = """
@startuml
class Customer {
  +id: int
}
class Order {
  +total: float
}
Customer --> Order
@enduml
"""
    result = validate_diagram(code, "flowchart")
    assert not result.ok
    assert any("class diagram" in m.lower() or "activity" in m.lower() for m in result.messages)


def test_valid_flowchart_passes():
    code = """
@startuml
start
:Receive request;
if (OK?) then (yes)
  :Process;
else (no)
  :Reject;
endif
stop
@enduml
"""
    result = validate_diagram(code, "flowchart")
    assert result.ok


def test_sanitize_plantuml_dedupes_and_trims():
    from app.services.plantuml_validate import sanitize_plantuml_output

    messy = "@startuml\n@startuml\nclass A {\n  +id: int\n  +id: int\n  +id: int\n}\n@enduml"
    cleaned = sanitize_plantuml_output(messy)
    assert cleaned.lower().count("@startuml") == 1
    assert cleaned.count("+id: int") == 1
    assert "@enduml" in cleaned.lower()
