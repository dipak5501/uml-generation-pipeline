"""Mock provider and repair smoke tests."""

from pathlib import Path

from app.providers.mock_provider import MockProvider
from app.services.repair import repair_plantuml
from app.settings import Settings


def test_mock_chat_returns_plantuml_for_class():
    p = MockProvider()
    out = p.chat("You are a UML expert for class diagrams.", "Bookstore cart checkout inventory")
    assert "@startuml" in out.lower()
    assert "class" in out.lower()


def test_mock_vision_score_in_range(tmp_path: Path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    score = MockProvider().vision_score(img, "score please")
    assert 0 <= score <= 6


def test_repair_with_mock_settings(monkeypatch):
    settings = Settings(mock_providers=True)
    broken = "@startuml\npackage core {\ncore ..> core\n@enduml"
    result = repair_plantuml(
        broken,
        "A simple core/api system",
        "package",
        ["Self-referential dependency"],
        settings=settings,
    )
    assert "@startuml" in result.code.lower()
    assert "@enduml" in result.code.lower()
