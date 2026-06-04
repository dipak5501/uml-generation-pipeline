from __future__ import annotations

from typing import Iterable


def weighted_composite(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
) -> float | None:
    """MMMU-weighted average over valid VLM scores (>0)."""
    num = 0.0
    den = 0.0
    for model, score in scores.items():
        if score is None:
            continue
        s = float(score)
        if s <= 0:
            continue
        w = weights.get(model, 1.0)
        num += s * w
        den += w
    if den == 0:
        return None
    return num / den


def normalize_vlm_keys(row: dict) -> dict[str, float | int | None]:
    mapping = {
        "qwen25vl3b": row.get("qwen25vl3b"),
        "llama32vl11b": row.get("llama32vl11b"),
        "aya_vision_8b": row.get("aya_vision_8b"),
    }
    return {k: (int(v) if v is not None and v != "" else None) for k, v in mapping.items()}


def recompute_composite(row: dict, weights: dict[str, float]) -> float | None:
    return weighted_composite(normalize_vlm_keys(row), weights)


def score_distribution(values: Iterable[float | int]) -> dict[int, int]:
    dist: dict[int, int] = {i: 0 for i in range(7)}
    for v in values:
        if v is None:
            continue
        bucket = max(0, min(6, int(round(float(v)))))
        dist[bucket] += 1
    return dist
