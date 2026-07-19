"""Unit tests for composite scoring + majority-vote gate (thesis formulas)."""

from app.services.cot import finalize_plantuml_output, has_cot_block
from app.services.scoring import (
    dataset_entry_accepted,
    formula_snapshot,
    majority_vote_accept,
    paper_composite,
    strip_private_reasoning,
    verify_scores,
)


WEIGHTS = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}


def test_composite_weighted_average():
    scores = {"qwen25vl3b": 6, "llama32vl11b": 4, "aya_vision_8b": 2}
    expected = (6 * 53.1 + 4 * 50.7 + 2 * 39.9) / (53.1 + 50.7 + 39.9)
    assert abs(paper_composite(scores, WEIGHTS) - expected) < 1e-9


def test_composite_includes_zero_skips_none():
    """Thesis render-gate form: numeric zeros still participate; None is skipped."""
    scores = {"qwen25vl3b": 0, "llama32vl11b": None, "aya_vision_8b": 5}
    expected = (0 * 53.1 + 5 * 39.9) / (53.1 + 39.9)
    assert abs(paper_composite(scores, WEIGHTS) - expected) < 1e-9


def test_composite_render_fail_is_zero():
    scores = {"qwen25vl3b": 6, "llama32vl11b": 5, "aya_vision_8b": 4}
    assert paper_composite(scores, WEIGHTS, render_ok=False) == 0.0


def test_majority_vote_tau_four():
    ok, votes, voters = majority_vote_accept(
        {"qwen25vl3b": 5, "llama32vl11b": 4, "aya_vision_8b": 3},
        tau=4,
    )
    assert ok is True
    assert votes == 2
    assert voters == ["qwen25vl3b", "llama32vl11b"]


def test_majority_rejects_when_under_two():
    ok, votes, _ = majority_vote_accept(
        {"qwen25vl3b": 5, "llama32vl11b": 3, "aya_vision_8b": 2},
        tau=4,
    )
    assert ok is False
    assert votes == 1


def test_dataset_gate_requires_majority_and_min_composite():
    assert dataset_entry_accepted(
        render_ok=True, composite=3.2, majority_accepted=True
    )
    assert not dataset_entry_accepted(
        render_ok=True, composite=2.9, majority_accepted=True
    )
    assert not dataset_entry_accepted(
        render_ok=True, composite=5.0, majority_accepted=False
    )
    assert not dataset_entry_accepted(
        render_ok=False, composite=5.0, majority_accepted=True
    )


def test_verify_scores_dual_signal():
    scores = {"qwen25vl3b": 5, "llama32vl11b": 4, "aya_vision_8b": 3}
    result = verify_scores(scores, WEIGHTS, render_ok=True, tau=4, min_composite=3.0)
    assert result.majority_accepted is True
    assert result.affirmative_votes == 2
    assert result.composite >= 3.0
    assert result.dataset_accepted is True
    assert "majority=True" in result.formula_snapshot


def test_legacy_weighted_composite_includes_zero():
    from uml_pipeline.scoring import weighted_composite

    scores = {"qwen25vl3b": 0, "llama32vl11b": 4, "aya_vision_8b": 2}
    expected = (0 * 53.1 + 4 * 50.7 + 2 * 39.9) / (53.1 + 50.7 + 39.9)
    assert abs(weighted_composite(scores, WEIGHTS) - expected) < 1e-9


def test_formula_snapshot_contains_final():
    scores = {"qwen25vl3b": 3}
    snap = formula_snapshot(scores, {"qwen25vl3b": 53.1}, 3.0)
    assert "final=3.0000" in snap
    assert "qwen25vl3b=3" in snap


def test_strip_private_reasoning_and_cot():
    raw = (
        "<think>\nplan entities and connectors\n</think>\n"
        "@startuml\nclass Foo\n@enduml\n"
    )
    assert has_cot_block(raw)
    cleaned = strip_private_reasoning(raw)
    assert "<think>" not in cleaned.lower()
    assert "class Foo" in cleaned
    final = finalize_plantuml_output(raw)
    assert final.startswith("@startuml")
    assert "class Foo" in final
    assert "</think>" not in final
