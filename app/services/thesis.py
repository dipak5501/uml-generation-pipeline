"""Thesis-committee briefing: paper numbers vs this Mac Studio, frozen eval snapshot."""

from __future__ import annotations

import math
import random
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from app.models import HumanReview, Reviewer, UMLArtifact
from app.schemas import ALL_DIAGRAM_TYPES
from app.services.package_failures import package_failure_report

# Paper Table I / RQ1 (DeepSeek-R1-Distill-Qwen-32B pipeline, n=2000 per type).
# These are NOT re-measured on the Mac Studio LoRA stack.
PAPER_BY_TYPE: dict[str, dict[str, float]] = {
    "class": {"success_pct": 95.7, "mean_s": 4.31, "sd": 0.74, "failures": 87, "pearson_r": 0.82, "kappa": 0.74},
    "object": {"success_pct": 94.4, "mean_s": 4.09, "sd": 0.81, "failures": 112, "pearson_r": 0.76, "kappa": 0.71},
    "component": {"success_pct": 91.6, "mean_s": 3.87, "sd": 0.93, "failures": 169, "pearson_r": 0.68, "kappa": 0.65},
    "package": {"success_pct": 81.1, "mean_s": 3.12, "sd": 1.04, "failures": 379, "pearson_r": 0.55, "kappa": 0.58},
}
PAPER_OVERALL = {
    "n": 8000,
    "success_pct": 94.4,
    "mean_s": 3.85,
    "majority_accept_pct": 91.3,
    "pearson_r": 0.71,
    "kappa": 0.68,
    "stage2_model": "DeepSeek-R1-Distill-Qwen-32B",
    "human_n_diagrams": 40,
    "human_n_raters": 80,
}

LIVE_STACK = {
    "host": "Math department Mac Studio (M1 Ultra, 128 GB) — production server",
    "stage1": "Ollama llama3.2:1b",
    "stage2": "MLX LoRA Qwen2.5-0.5B (uml-plantuml-lora-sourcecode-30k)",
    "vlms": "Qwen2.5-VL-3B + LLaMA-3.2-Vision-11B + Aya-Vision-8B",
    "note": (
        "Architecture, gates, and VLM ensemble match the thesis. "
        "Numeric parity with the paper's 32B tables is not claimed on this stack."
    ),
}

PARKING_REQUIREMENT = (
    "Campus parking office: students and staff register vehicles, purchase permits, "
    "and receive citations for violations. Officers record citations against a vehicle "
    "and a permit. A payment clerk records payments. The system tracks lots, spaces, "
    "and whether a permit is valid for a given lot."
)

LIBRARY_JAVA = """\
public class Book {
    private String isbn;
    private String title;
    public String getTitle() { return title; }
}
public class Member {
    private String memberId;
    private String email;
    public void borrow(Loan loan) { }
}
public class Loan {
    private Book book;
    private Member member;
    public Book getBook() { return book; }
}
public class LibraryService {
    public Loan checkout(Member member, Book book) { return new Loan(); }
}
"""

DEMO_CASES: list[dict[str, Any]] = [
    {
        "id": "rq1-nl-class",
        "rq": "RQ1",
        "title": "Natural-language class diagram (campus parking)",
        "requirement": PARKING_REQUIREMENT,
        "diagram_type": "class",
        "diagram_types": ["class"],
        "input_mode": "requirement",
        "why": "Shows Stage 1–3 on a design-phase class diagram with S, A, and the dataset gate.",
    },
    {
        "id": "rq1-java-four",
        "rq": "RQ1",
        "title": "Java source → class, object, component, package",
        "requirement": LIBRARY_JAVA,
        "diagram_type": "class",
        "diagram_types": ["class", "object", "component", "package"],
        "input_mode": "source_code",
        "why": "One source file, four design-phase types — the committee can compare S and render across RQ3's difficulty order.",
    },
    {
        "id": "rq3-package",
        "rq": "RQ3",
        "title": "Package diagram (hardest type)",
        "requirement": PARKING_REQUIREMENT,
        "diagram_type": "package",
        "diagram_types": ["package"],
        "input_mode": "requirement",
        "why": "Package is the weakest family in the paper (81.1% render, mean S 3.12). Inspect failures here.",
    },
]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    value = float(pd.Series(xs).corr(pd.Series(ys), method="pearson"))
    return None if math.isnan(value) else value


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    value = float(pd.Series(xs).corr(pd.Series(ys), method="spearman"))
    return None if math.isnan(value) else value


def human_score_on_six(review: HumanReview) -> float:
    """Map a human review onto the paper's 0–6 scale."""
    mean = (
        review.semantic_correctness
        + review.structural_completeness
        + review.syntactic_accuracy
        + review.overall_coherence
    ) / 4.0
    scale = int(getattr(review, "score_scale", 6) or 6)
    if scale == 5:
        return (mean - 1.0) * (6.0 / 4.0)
    return mean


def live_type_stats(artifacts: list[UMLArtifact]) -> dict[str, dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for dtype in ALL_DIAGRAM_TYPES:
        rows = [a for a in artifacts if a.diagram_type == dtype]
        n = len(rows)
        success = sum(1 for a in rows if a.render_status == "success")
        scores = [a.composite_score for a in rows]
        maj = sum(1 for a in rows if a.majority_accepted)
        ds = sum(1 for a in rows if a.dataset_accepted)
        by[dtype] = {
            "n": n,
            "success_pct": (100.0 * success / n) if n else None,
            "mean_s": (sum(scores) / n) if n else None,
            "majority_accept_pct": (100.0 * maj / n) if n else None,
            "dataset_accept_pct": (100.0 * ds / n) if n else None,
            "failures": n - success,
        }
    return by


def human_alignment(session: Session) -> dict[str, Any]:
    reviews = session.exec(select(HumanReview)).all()
    pairs: list[tuple[str, float, float, int]] = []
    for rev in reviews:
        art = session.get(UMLArtifact, rev.artifact_id)
        if art is None:
            continue
        pairs.append(
            (art.diagram_type, float(art.composite_score), human_score_on_six(rev), rev.reviewer_id)
        )
    xs = [p[1] for p in pairs]
    ys = [p[2] for p in pairs]
    by_type: dict[str, Any] = {}
    for dtype in ALL_DIAGRAM_TYPES:
        sub = [p for p in pairs if p[0] == dtype]
        by_type[dtype] = {
            "n": len(sub),
            "pearson_r": _pearson([p[1] for p in sub], [p[2] for p in sub]),
            "spearman_rho": _spearman([p[1] for p in sub], [p[2] for p in sub]),
        }
    raters = {p[3] for p in pairs}
    return {
        "n_reviews": len(reviews),
        "n_pairs": len(pairs),
        "n_raters": len(raters),
        "pearson_r": _pearson(xs, ys),
        "spearman_rho": _spearman(xs, ys),
        "by_diagram_type": by_type,
        "fleiss_kappa": None,
        "note": (
            "Human sliders are 0–6 to match VLMs. Fleiss' κ needs ≥2 independent raters "
            "per diagram; it stays empty until a real multi-rater study is saved. "
            "Do not quote the paper's r=0.71 / 80-rater table as a live-server result."
        ),
    }


def stratified_snapshot(
    session: Session,
    *,
    seed: int = 42,
    n_per_type: int = 10,
) -> dict[str, Any]:
    """Frozen evaluation set: up to n_per_type artifacts per diagram type (seed 42)."""
    rng = random.Random(seed)
    items: list[dict[str, Any]] = []
    shortfall: dict[str, int] = {}
    for dtype in ALL_DIAGRAM_TYPES:
        rows = list(
            session.exec(select(UMLArtifact).where(UMLArtifact.diagram_type == dtype)).all()
        )
        rng.shuffle(rows)
        chosen = rows[:n_per_type]
        if len(chosen) < n_per_type:
            shortfall[dtype] = n_per_type - len(chosen)
        for a in chosen:
            items.append(
                {
                    "id": a.id,
                    "diagram_type": a.diagram_type,
                    "input_mode": a.input_mode,
                    "source_language": a.source_language,
                    "source_requirement": (a.source_requirement or "")[:2000],
                    "plantuml_code": a.plantuml_code or "",
                    "render_status": a.render_status,
                    "composite_score": a.composite_score,
                    "majority_accepted": a.majority_accepted,
                    "dataset_accepted": a.dataset_accepted,
                    "affirmative_votes": a.affirmative_votes,
                }
            )
    return {
        "seed": seed,
        "n_per_type": n_per_type,
        "target_n": n_per_type * len(ALL_DIAGRAM_TYPES),
        "actual_n": len(items),
        "shortfall": shortfall,
        "items": items,
        "note": (
            "Stratified sample from this Mac Studio SQLite DB (not the paper's 8k DeepSeek run). "
            "Use this CSV/JSON as the take-home committee artifact."
        ),
    }


def committee_briefing(session: Session) -> dict[str, Any]:
    artifacts = session.exec(select(UMLArtifact)).all()
    n = len(artifacts)
    success = sum(1 for a in artifacts if a.render_status == "success")
    maj = sum(1 for a in artifacts if a.majority_accepted)
    ds = sum(1 for a in artifacts if a.dataset_accepted)
    scores = [a.composite_score for a in artifacts]
    live = {
        "n": n,
        "success_pct": (100.0 * success / n) if n else None,
        "mean_s": (sum(scores) / n) if n else None,
        "majority_accept_pct": (100.0 * maj / n) if n else None,
        "dataset_accept_pct": (100.0 * ds / n) if n else None,
        "by_diagram_type": live_type_stats(artifacts),
    }
    return {
        "research_questions": [
            {
                "id": "RQ1",
                "text": "How effectively can a decomposed LLM pipeline generate valid UML from requirements at scale?",
                "where": "Thesis Defense → Run parking class + Java four-type demos. Read S, A, render.",
            },
            {
                "id": "RQ2",
                "text": "To what degree does the VLM ensemble correlate with human evaluation?",
                "where": "Human Evaluation (0–6) then Analytics / this briefing. Live correlation is only defined after reviews are saved.",
            },
            {
                "id": "RQ3",
                "text": "How does accuracy vary across class, object, component, and package?",
                "where": "Live-by-type table below + package failure gallery. Paper order: class > object > component > package.",
            },
        ],
        "paper": {"overall": PAPER_OVERALL, "by_diagram_type": PAPER_BY_TYPE},
        "live": live,
        "live_stack": LIVE_STACK,
        "human_alignment": human_alignment(session),
        "package_failures": package_failure_report(session),
        "demo_cases": DEMO_CASES,
        "formula": {
            "S": "S = δ · Σ w_j s_j / Σ w_j,  w = (53.1, 50.7, 39.9),  δ=0 if render fails",
            "A": "A = 1 if at least 2 of 3 VLMs score ≥ τ=4",
            "dataset": "dataset accepted iff render OK ∧ A=1 ∧ S≥3",
        },
    }
