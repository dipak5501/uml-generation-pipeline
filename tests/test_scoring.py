"""Unit tests for composite scoring (paper formula)."""

from app.services.scoring import formula_snapshot, paper_composite


def test_composite_weighted_average():
    scores = {"qwen25vl3b": 6, "llama32vl11b": 4, "aya_vision_8b": 2}
    weights = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}
    expected = (6 * 53.1 + 4 * 50.7 + 2 * 39.9) / (53.1 + 50.7 + 39.9)
    assert abs(paper_composite(scores, weights) - expected) < 1e-9


def test_composite_ignores_zero_and_none():
    scores = {"qwen25vl3b": 0, "llama32vl11b": None, "aya_vision_8b": 5}
    weights = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}
    assert paper_composite(scores, weights) == 5.0


def test_composite_all_invalid_is_zero():
    scores = {"qwen25vl3b": 0, "llama32vl11b": 0, "aya_vision_8b": None}
    weights = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}
    assert paper_composite(scores, weights) == 0.0


def test_formula_snapshot_contains_final():
    scores = {"qwen25vl3b": 3}
    weights = {"qwen25vl3b": 53.1}
    snap = formula_snapshot(scores, weights, 3.0)
    assert "final=3.0000" in snap
    assert "qwen25vl3b=3" in snap
