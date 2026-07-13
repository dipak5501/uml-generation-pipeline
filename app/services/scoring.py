"""Composite scoring helpers (MMMU-weighted formula from the paper)."""

from __future__ import annotations

from uml_pipeline.scoring import weighted_composite as _weighted_composite


def paper_composite(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
) -> float:
    """
    valid_scores = [(score_i, weight_i) for each model where score_i > 0]
    final_score = 0 if empty else sum(score_i * weight_i) / sum(weight_i)
    """
    value = _weighted_composite(scores, weights)
    return 0.0 if value is None else float(value)


def formula_snapshot(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
    final: float,
) -> str:
    parts = []
    for k, s in scores.items():
        if s is None:
            continue
        parts.append(f"{k}={s}(w={weights.get(k, 0)})")
    return "final=" + f"{final:.4f}" + " | " + ", ".join(parts)
