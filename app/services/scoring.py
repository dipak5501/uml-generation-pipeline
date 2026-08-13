"""Paper-faithful scoring: MMMU-weighted composite + majority-vote gate."""

from __future__ import annotations

from dataclasses import dataclass

from uml_pipeline.scoring import weighted_composite as _weighted_composite


DEFAULT_TAU = 4
DEFAULT_MIN_COMPOSITE_FOR_DATASET = 3.0


def paper_composite(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
    *,
    render_ok: bool = True,
) -> float:
    """
    Thesis Eq. (weighted):
      if render fails: S = 0
      else: S = sum(w_j * s_j) / sum(w_j) over all models with numeric scores

    Unavailable models (None) are skipped so a missing scorer does not crash scoring.
    Scores of 0 from an available scorer still participate when render_ok is True,
    matching the thesis render-gate formulation.
    """
    if not render_ok:
        return 0.0

    num = 0.0
    den = 0.0
    for model, score in scores.items():
        if score is None:
            continue
        s = float(score)
        w = float(weights.get(model, 1.0))
        num += s * w
        den += w
    if den == 0:
        # Fall back to >0-only average if nothing numeric was provided
        value = _weighted_composite(scores, weights)
        return 0.0 if value is None else float(value)
    return num / den


def majority_vote_accept(
    scores: dict[str, float | int | None],
    *,
    tau: float = DEFAULT_TAU,
    min_votes: int = 2,
) -> tuple[bool, int, list[str]]:
    """
    Thesis Eq. (majority):
      v_j = 1 if s_j >= tau else 0
      A = 1 if sum(v_j) >= 2
    Returns (accepted, affirmative_votes, voter_keys_that_accepted).
    """
    voters: list[str] = []
    for key, score in scores.items():
        if score is None:
            continue
        if float(score) >= tau:
            voters.append(key)
    return len(voters) >= min_votes, len(voters), voters


def dataset_entry_accepted(
    *,
    render_ok: bool,
    composite: float,
    majority_accepted: bool,
    min_composite: float = DEFAULT_MIN_COMPOSITE_FOR_DATASET,
) -> bool:
    """Paper rule: enter final dataset only if A_i = 1 and S_i >= 3.0 (and render OK)."""
    return bool(render_ok and majority_accepted and composite >= min_composite)


@dataclass
class VerificationResult:
    composite: float
    majority_accepted: bool
    affirmative_votes: int
    accepting_models: list[str]
    dataset_accepted: bool
    tau: float
    min_composite: float
    formula_snapshot: str


def verify_scores(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
    *,
    render_ok: bool,
    tau: float = DEFAULT_TAU,
    min_composite: float = DEFAULT_MIN_COMPOSITE_FOR_DATASET,
    min_votes: int = 2,
) -> VerificationResult:
    composite = paper_composite(scores, weights, render_ok=render_ok)
    maj_ok, votes, voters = majority_vote_accept(scores, tau=tau, min_votes=min_votes)
    if not render_ok:
        maj_ok = False
        votes = 0
        voters = []
    accepted = dataset_entry_accepted(
        render_ok=render_ok,
        composite=composite,
        majority_accepted=maj_ok,
        min_composite=min_composite,
    )
    snap = formula_snapshot(scores, weights, composite, maj_ok, votes, accepted, tau)
    return VerificationResult(
        composite=composite,
        majority_accepted=maj_ok,
        affirmative_votes=votes,
        accepting_models=voters,
        dataset_accepted=accepted,
        tau=tau,
        min_composite=min_composite,
        formula_snapshot=snap,
    )


def formula_snapshot(
    scores: dict[str, float | int | None],
    weights: dict[str, float],
    final: float,
    majority_accepted: bool = False,
    affirmative_votes: int = 0,
    dataset_accepted: bool = False,
    tau: float = DEFAULT_TAU,
) -> str:
    parts = []
    for k, s in scores.items():
        if s is None:
            parts.append(f"{k}=na")
            continue
        vote = "Y" if float(s) >= tau else "N"
        parts.append(f"{k}={s}(w={weights.get(k, 0)},vote={vote})")
    return (
        f"final={final:.4f} | majority={majority_accepted} "
        f"votes={affirmative_votes} tau={tau} | dataset_accepted={dataset_accepted} | "
        + ", ".join(parts)
    )


def strip_private_reasoning(text: str) -> str:
    """Remove paper-style <think>...</think> (and similar) blocks; keep final PlantUML only."""
    import re

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"```(?:plantuml)?\s*", "", cleaned)
    cleaned = re.sub(r"```", "", cleaned)
    return cleaned.strip()
