"""Golden + unit tests for multi-layer UML acceptance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.acceptance import evaluate_acceptance
from app.services.plantuml_from_spec import plantuml_from_spec
from app.services.plantuml_validate import validate_diagram
from app.services.repair import repair_plantuml
from app.services.spec_json import ensure_valid_spec, extract_named_concepts
from app.services.traceability import evaluate_semantics
from app.services.uml_structure import validate_uml_structure
from app.settings import Settings, get_settings
from uml_pipeline.render import check_plantuml_syntax, render_plantuml

GOLDEN = Path(__file__).parent / "golden" / "cases.json"


def _generate(requirement: str, diagram_type: str) -> tuple[str, dict]:
    spec, _, _ = ensure_valid_spec(requirement, diagram_type, source_text=requirement)
    return plantuml_from_spec(spec, diagram_type), spec


def test_extracts_lowercase_domain_nouns():
    names = extract_named_concepts(
        "Build an online bookstore with inventory management, shopping carts, and order checkout."
    )
    lowered = {n.lower() for n in names}
    assert "bookstore" in lowered
    assert "inventory" in lowered
    assert "cart" in lowered
    assert "order" in lowered or "checkout" in lowered
    assert "build" not in lowered


def test_library_concepts_still_extracted():
    names = extract_named_concepts(
        "Library management system with classes Book, Member, Loan, and Librarian. "
        "A Member borrows a Book through a Loan."
    )
    for required in ("Book", "Member", "Loan", "Librarian"):
        assert required in names


def test_empty_class_fails_structure():
    result = validate_uml_structure("@startuml\n@enduml\n", "class")
    assert not result.ok


def test_sequence_not_supported():
    result = validate_uml_structure("@startuml\nAlice -> Bob: hi\n@enduml\n", "sequence")
    assert not result.ok


def test_hallucinated_entity_fails_semantics():
    req = "Library system with Book and Member."
    uml = """@startuml
class Book
class Member
class UnicornLauncher
class QuantumRouter
class DragonService
Book --> Member
@enduml
"""
    sem = evaluate_semantics(requirement=req, plantuml=uml, diagram_type="class")
    assert not sem.hallucination_ok
    assert not sem.ok


def test_missing_required_concepts_fail_completeness():
    req = "Library management system with classes Book, Member, Loan, and Librarian."
    uml = """@startuml
class Widget
class Gadget
Widget --> Gadget
@enduml
"""
    sem = evaluate_semantics(requirement=req, plantuml=uml, diagram_type="class")
    assert not sem.completeness_ok
    assert "Book" in sem.missing


def test_syntax_repair_closes_braces():
    settings = Settings(mock_providers=True)
    broken = "@startuml\npackage Core {\n  class Account\n@enduml\n"
    result = repair_plantuml(
        broken,
        "Banking with Account",
        "package",
        ["Unbalanced curly braces"],
        settings=settings,
        category="syntax",
    )
    assert result.code.count("{") == result.code.count("}")
    assert "@enduml" in result.code.lower()


def test_adaptive_missing_element_rebuilds_from_spec():
    settings = Settings(mock_providers=True)
    spec, _, _ = ensure_valid_spec(
        "Library management system with classes Book, Member, Loan, and Librarian.",
        "class",
    )
    weak = "@startuml\nclass Widget\n@enduml\n"
    result = repair_plantuml(
        weak,
        "Library management system with classes Book, Member, Loan, and Librarian.",
        "class",
        ["Missing required concepts: Book, Member, Loan"],
        settings=settings,
        category="missing_element",
        spec_json=spec,
    )
    assert "Book" in result.code
    assert "Member" in result.code


@pytest.mark.parametrize("case", json.loads(GOLDEN.read_text(encoding="utf-8")))
def test_golden_cases_accept(case, tmp_path):
    plantuml, spec = _generate(case["requirement"], case["diagram_type"])
    syntax = validate_diagram(plantuml, case["diagram_type"])
    assert syntax.ok, syntax.messages

    settings = get_settings()
    compile_ok, compile_err = check_plantuml_syntax(plantuml, settings.plantuml_jar, work_dir=tmp_path)
    assert compile_ok, compile_err

    img, err = render_plantuml(plantuml, tmp_path, settings.plantuml_jar, fmt="png")
    assert img is not None, err

    report = evaluate_acceptance(
        requirement=case["requirement"],
        plantuml=plantuml,
        diagram_type=case["diagram_type"],
        spec=spec,
        render_ok=True,
    )
    expected = case["expected"]
    for name in expected.get("classes") or expected.get("types") or expected.get("packages") or expected.get("components") or []:
        assert name.lower() in plantuml.lower(), f"{case['id']} missing {name}"
    for rel in expected.get("inheritance") or []:
        assert rel in plantuml, f"{case['id']} missing {rel}"
    assert report.syntax_ok, report.to_dict()
    assert report.compile_ok is not False, report.to_dict()
    assert report.uml_rules_ok, report.to_dict()
    assert report.semantic_ok, report.to_dict()
    assert report.accepted, report.to_dict()


def test_acceptance_rejects_unrendered():
    plantuml, spec = _generate(
        "Library management system with classes Book, Member, Loan, and Librarian.",
        "class",
    )
    report = evaluate_acceptance(
        requirement="Library management system with classes Book, Member, Loan, and Librarian.",
        plantuml=plantuml,
        diagram_type="class",
        spec=spec,
        render_ok=False,
        run_compile=False,
    )
    assert not report.accepted
    assert report.failure_category == "render"
