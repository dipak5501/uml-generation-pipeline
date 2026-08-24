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


def test_parse_markdown_semantic_score():
    from uml_pipeline.llm_client import extract_vlm_score

    score, explanation = parse_score_response("**SEMANTIC: 5**\nThe classes match the spec.")
    assert score == 5
    assert explanation is not None
    extracted, _ = extract_vlm_score("**SEMANTIC: 5**")
    assert extracted == 5


def test_parse_markdown_score_line():
    score, _ = parse_score_response("**SCORE: 4**\nEXPLANATION: layout is readable")
    assert score == 4


def test_placeholder_range_is_not_a_real_zero():
    from uml_pipeline.llm_client import extract_vlm_score, _score_from_vlm_text
    import pytest

    text = "SEMANTIC: <0-6>\nEXPLANATION: template not filled"
    score, _ = extract_vlm_score(text)
    assert score is None
    # Compat helper still defaults to 0, but live scorers must raise.
    assert parse_score_response(text)[0] == 0
    with pytest.raises(RuntimeError, match="unparseable"):
        _score_from_vlm_text(text)


def test_real_score_wins_over_placeholder_in_prompt_echo():
    text = "SCORE: <integer 0-6>\nSEMANTIC: 5\nEXPLANATION: entities present"
    score, explanation = parse_score_response(text)
    assert score == 5
    assert explanation is not None
