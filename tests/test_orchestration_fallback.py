"""Tests for fine-tuned output quality gates and source-code provider routing."""

from app.services.orchestration import _finetuned_output_needs_fallback


def test_generic_classes_need_fallback():
    code = "@startuml\nclass Detected {\n}\nclass Language {\n}\n@enduml"
    assert _finetuned_output_needs_fallback(code, "### Entities\n- User: id", validation_ok=True)


def test_spec_aligned_classes_ok():
    code = "@startuml\nclass User {\n}\nclass Order {\n}\n@enduml"
    assert not _finetuned_output_needs_fallback(
        code, "### Entities\n- User: id\n- Order: total", validation_ok=True
    )


def test_invalid_syntax_needs_fallback():
    code = "@startuml\npackage x {\nclass A\n@enduml"
    assert _finetuned_output_needs_fallback(code, "### Entities\n- A: id", validation_ok=False)
