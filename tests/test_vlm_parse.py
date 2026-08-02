"""Tests for VLM SCORE/EXPLANATION parsing."""

from uml_pipeline.llm_client import parse_score_response


def test_parse_structured_score_and_explanation():
    text = """SCORE: 5
EXPLANATION: Entities match the spec. Structure is mostly complete with one missing association. Notation is valid PlantUML. Layout is clear."""
    score, explanation = parse_score_response(text)
    assert score == 5
    assert explanation is not None
    assert "Entities match" in explanation
    assert "Layout is clear" in explanation


def test_parse_bare_integer_fallback():
    score, explanation = parse_score_response("The diagram scores 4 overall.")
    assert score == 4
    assert explanation is not None
    assert "scores 4" in explanation


def test_parse_missing_defaults_zero():
    score, explanation = parse_score_response("no numeric score here")
    assert score == 0
    assert explanation == "no numeric score here"
