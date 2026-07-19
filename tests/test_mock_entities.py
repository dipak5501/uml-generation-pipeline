"""Mock provider should extract domain entities, not modal verbs."""

from app.providers.mock_provider import MockProvider, _entities_from_text


PAPER_REQ = (
    "The system shall allow students to register for courses, instructors to "
    "manage course offerings, and administrators to monitor enrollment limits."
)


def test_paper_requirement_entities_skip_shall():
    ents = _entities_from_text(
        f"Software requirement:\n{PAPER_REQ}\n\nTarget diagram type: class",
        n=5,
    )
    lower = {e.lower() for e in ents}
    assert "shall" not in lower
    assert "register" not in lower
    assert "student" in lower
    assert "course" in lower
    assert "instructor" in lower
    assert "administrator" in lower


def test_mock_spec_for_paper_requirement():
    spec = MockProvider().chat(
        "You are a senior system architect. Output only the technical specification.",
        f"Software requirement:\n{PAPER_REQ}\n\nTarget diagram type: class",
    )
    assert "Shall:" not in spec
    assert "Student" in spec
    assert "Course" in spec
    assert "Instructor" in spec
    assert "Administrator" in spec


def test_mock_plantuml_uses_domain_classes():
    p = MockProvider()
    out = p.chat(
        "You are a UML expert. Output only valid PlantUML between @startuml and @enduml.",
        f"Technical specification:\n## Spec\n### Entities\n"
        f"- Student: id\n- Course: id\n- Instructor: id\n- Administrator: id\n",
    )
    assert "@startuml" in out.lower()
    assert "Student" in out
    assert "Shall" not in out
