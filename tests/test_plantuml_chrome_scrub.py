"""PlantUML chrome scrub / brace repair for package title {} failures."""

from app.services.plantuml_validate import sanitize_plantuml_output, scrub_empty_plantuml_chrome


def test_scrub_drops_empty_title_braces():
    code = """@startuml
title {}
note as DiagramGuide
  What this shows: {}
end note
package Campus {
  class Campus
}
@enduml
"""
    out = scrub_empty_plantuml_chrome(code)
    assert "title {}" not in out
    assert "package Campus {" in out
    assert "design overview" in out


def test_sanitize_removes_orphan_closers_after_bad_title():
    code = """@startuml
title {
note as DiagramGuide
  What this shows: {
  Where it fits: Design
end note
package System {
  package MenuItem {
    class MenuItem
  }
}
MenuItem ..> Other : depends
}}
@enduml
"""
    out = sanitize_plantuml_output(code, diagram_type="package")
    assert "title {" not in out
    assert out.count("{") == out.count("}")
    assert "package System {" in out
    assert "}}\n@enduml" not in out.replace(" ", "")
