"""Tests for VLM SCORE/EXPLANATION parsing."""

from uml_pipeline.llm_client import parse_score_response, score_response_parsed


def test_parse_structured_score_and_explanation():
    text = """SCORE: 5
EXPLANATION: Entities match the spec. Structure is mostly complete with one missing association. Notation is valid PlantUML. Layout is clear."""
    score, explanation = parse_score_response(text)
    assert score == 5
    assert explanation is not None
    assert "Entities match" in explanation
    assert "Layout is clear" in explanation
    assert score_response_parsed(text)


def test_parse_bare_integer_fallback():
    score, explanation = parse_score_response("The diagram scores 4 overall.")
    assert score == 4
    assert explanation is not None
    assert "scores 4" in explanation


def test_parse_missing_defaults_zero():
    score, explanation = parse_score_response("no numeric score here")
    assert score == 0
    assert explanation == "no numeric score here"
    assert not score_response_parsed("no numeric score here")


def test_parse_markdown_semantic_score():
    from uml_pipeline.llm_client import extract_vlm_score

    score, explanation = parse_score_response("**SEMANTIC: 5**\nThe classes match the spec.")
    assert score == 5
    assert explanation is not None
    extracted, _ = extract_vlm_score("**SEMANTIC: 5**")
    assert extracted == 5
    assert score_response_parsed("**SEMANTIC: 5**\nLooks good.")


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


def test_parse_placeholder_range_not_zero_score():
    # Instructional <0-6> must not be treated as a numeric score of 0.
    score, explanation = parse_score_response(
        "Reply as SEMANTIC: <0-6>\nThe diagram quality is excellent (score 4)."
    )
    assert score == 4


def test_real_score_wins_over_placeholder_in_prompt_echo():
    text = "SCORE: <integer 0-6>\nSEMANTIC: 5\nEXPLANATION: entities present"
    score, explanation = parse_score_response(text)
    assert score == 5
    assert explanation is not None


def test_parse_prefers_score_over_criterion_labels():
    # Multi-axis replies: overall SCORE must win over the first SEMANTIC line.
    text = """SEMANTIC: 5
STRUCTURAL: 2
SYNTACTIC: 4
COHERENCE: 3
SCORE: 3
EXPLANATION: Structure is incomplete despite strong entity naming."""
    score, explanation = parse_score_response(text)
    assert score == 3
    assert explanation is not None
    assert "incomplete" in explanation
    assert score_response_parsed(text)


def test_parse_averages_criteria_when_score_missing():
    text = """SEMANTIC: 6
STRUCTURAL: 4
SYNTACTIC: 5
COHERENCE: 5
EXPLANATION: Solid diagram with one structural gap."""
    score, explanation = parse_score_response(text)
    assert score == 5  # round((6+4+5+5)/4) == 5
    assert "structural gap" in (explanation or "")


def test_parse_score_over_six_fraction():
    score, explanation = parse_score_response("SCORE: 4/6\nEXPLANATION: Mostly aligned.")
    assert score == 4
    assert "Mostly aligned" in (explanation or "")


def test_parse_last_score_wins():
    text = "SCORE: 2\nSCORE: 5\nEXPLANATION: Revised upward after re-check."
    score, _ = parse_score_response(text)
    assert score == 5


def test_parse_empty_unparsed():
    assert parse_score_response("") == (0, None)
    assert not score_response_parsed("")
    assert not score_response_parsed("   ")
