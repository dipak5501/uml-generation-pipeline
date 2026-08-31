"""Tests for PlantUML validators and package guards."""

import re

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


def test_repair_object_adds_type():
    from app.services.plantuml_validate import repair_object_declarations, sanitize_plantuml_output

    broken = """@startuml
object user1 {
  email = a@b.com
}
object order1
user1 --> order1
@enduml
"""
    fixed = sanitize_plantuml_output(broken, diagram_type="object")
    assert "object user1 : User" in fixed
    assert "object order1 : Order" in fixed
    assert validate_diagram(fixed, "object").ok
    # helper alone
    assert "object cart2 : Cart" in repair_object_declarations("object cart2 {")


def test_repair_package_nests_dotted_peers():
    from app.services.plantuml_validate import repair_package_nesting, sanitize_plantuml_output

    broken = """@startuml
package com.app.core {
  class Entity
}
package com.app.api {
  class Controller
}
com.app.api ..> com.app.core
@enduml
"""
    fixed = sanitize_plantuml_output(broken, diagram_type="package")
    assert "package com {" in fixed or "package com\n" in fixed.replace("  ", "")
    assert "package core {" in fixed
    assert "package api {" in fixed
    # No flat dotted package decls remaining
    assert not re.search(r"package\s+com\.app\.(core|api)\s*\{", fixed)
    assert validate_diagram(fixed, "package").ok
    nested = repair_package_nesting(broken)
    assert "package app {" in nested


def test_strip_plantuml_colors_and_publication_style():
    from app.services.plantuml_validate import (
        apply_publication_plantuml_style,
        strip_plantuml_colors,
    )

    colored = """@startuml
!theme cerulean
skinparam backgroundColor #EEFFEE
skinparam classBackgroundColor LightBlue
class User #Pink {
  +name: String
}
User --> Order : uses
@enduml
"""
    stripped = strip_plantuml_colors(colored)
    assert "!theme" not in stripped.lower()
    assert "skinparam" not in stripped.lower()
    assert "#" not in stripped

    styled = apply_publication_plantuml_style(colored)
    assert "skinparam monochrome true" in styled
    assert "class User" in styled
    assert validate_diagram(styled, "class").ok


def test_sanitize_injects_monochrome_skinparams():
    raw = """@startuml
skinparam backgroundColor #AABBCC
class Foo
@enduml
"""
    cleaned = sanitize_plantuml_output(raw, diagram_type="class")
    assert "skinparam monochrome true" in cleaned
    assert "#AABBCC" not in cleaned
    assert "class Foo" in cleaned

    from app.services.plantuml_from_spec import plantuml_from_spec

    spec = {
        "diagram_type": "object",
        "objects": [
            {"name": "alice", "type": "User", "values": ["email = a@b.com"]},
            {"name": "o1", "type": "Order"},
        ],
        "relationships": [{"source": "alice", "target": "o1", "type": "link"}],
    }
    code = plantuml_from_spec(spec, "object")
    assert "object alice : User" in code
    assert 'object "o1 : Order" as o1' in code
    assert validate_diagram(code, "object").ok


def test_component_builder_skips_invented_interfaces():
    from app.services.plantuml_from_spec import plantuml_from_spec

    spec = {
        "diagram_type": "component",
        "components": [{"name": "CartService"}, {"name": "PaymentService"}],
        "relationships": [
            {"source": "CartService", "target": "PaymentService", "type": "dependency"}
        ],
    }
    code = plantuml_from_spec(spec, "component")
    assert "ICartService" not in code and '() "ICart"' not in code
    assert "CartService" in code
    assert validate_diagram(code, "component").ok
