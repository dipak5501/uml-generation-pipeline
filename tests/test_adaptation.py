"""Self-adaptation policy and category-specific repair strategies."""

from __future__ import annotations

from pathlib import Path

from app.services.adaptation import (
    AdaptationMemory,
    choose_generator,
    choose_strategies,
)
from app.services.repair import (
    repair_plantuml,
    strategy_inject_missing,
    strategy_strip_hallucinations,
)
from app.settings import Settings


def test_policy_promotes_winning_strategy(tmp_path: Path):
    mem = AdaptationMemory(tmp_path / "mem.json")
    mem.record("strategies", "class|syntax", "spec_rebuild", ok=True)
    mem.record("strategies", "class|syntax", "spec_rebuild", ok=True)
    mem.record("strategies", "class|syntax", "spec_rebuild", ok=True)
    mem.record("strategies", "class|syntax", "sanitize_syntax", ok=False)
    mem.record("strategies", "class|syntax", "sanitize_syntax", ok=False)
    mem.record("strategies", "class|syntax", "sanitize_syntax", ok=False)
    ordered = choose_strategies("class", "syntax", memory=mem)
    assert ordered[0] == "spec_rebuild"
    skipped = choose_strategies("class", "syntax", tried=["spec_rebuild"], memory=mem)
    assert "spec_rebuild" not in skipped
    assert skipped[0] in {"sanitize_syntax", "llm_targeted"}


def test_policy_skips_losing_lora(tmp_path: Path):
    mem = AdaptationMemory(tmp_path / "mem.json")
    for _ in range(5):
        mem.record("generators", "package", "lora", ok=False)
    for _ in range(4):
        mem.record("generators", "package", "spec-builder", ok=True)
    settings = Settings(mock_providers=True, use_finetuned_code=True)
    choice, reason = choose_generator("package", settings=settings, memory=mem)
    assert choice == "spec-builder"
    assert "spec-builder" in reason or "grounded" in reason or "adapted" in reason


def test_strip_hallucinations_removes_extra_class():
    req = "Library system with Book and Member."
    uml = """@startuml
class Book
class Member
class UnicornLauncher
class DragonService
Book --> Member
UnicornLauncher --> Book
@enduml
"""
    spec = {
        "diagram_type": "class",
        "entities": [{"name": "Book"}, {"name": "Member"}],
        "relationships": [{"source": "Book", "target": "Member", "type": "association"}],
    }
    cleaned = strategy_strip_hallucinations(uml, spec_json=spec, specification=req)
    assert "UnicornLauncher" not in cleaned
    assert "DragonService" not in cleaned
    assert "Book" in cleaned
    assert "Member" in cleaned


def test_inject_missing_adds_required_class():
    req = "Library management system with classes Book, Member, Loan, and Librarian."
    uml = "@startuml\nclass Book\n@enduml\n"
    spec = {
        "diagram_type": "class",
        "entities": [{"name": "Book"}, {"name": "Member"}, {"name": "Loan"}, {"name": "Librarian"}],
        "relationships": [],
    }
    out = strategy_inject_missing(
        uml, spec_json=spec, specification=req, diagram_type="class", errors=["missing Member"]
    )
    assert "Member" in out
    assert "Loan" in out or "Librarian" in out


def test_repair_uses_named_strategy(tmp_path: Path, monkeypatch):
    mem = AdaptationMemory(tmp_path / "mem.json")
    settings = Settings(mock_providers=True)
    broken = "@startuml\npackage Core {\n  class Account\n@enduml\n"
    result = repair_plantuml(
        broken,
        "Banking with Account",
        "package",
        ["Unbalanced curly braces"],
        settings=settings,
        category="syntax",
        memory=mem,
    )
    assert result.strategy in {"sanitize_syntax", "spec_rebuild", "llm_targeted"}
    assert "@enduml" in result.code.lower()
    assert result.code.count("{") == result.code.count("}")
