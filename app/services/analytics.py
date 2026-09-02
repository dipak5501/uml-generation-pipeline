"""Analytics and export helpers."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from app.models import HumanReview, RepairAttempt, Reviewer, UMLArtifact
from app.services.package_failures import package_failure_report
from app.services.thesis import human_alignment


def analytics_summary(session: Session) -> dict[str, Any]:
    artifacts = session.exec(select(UMLArtifact)).all()
    by_type: dict[str, dict[str, Any]] = {}
    for a in artifacts:
        bucket = by_type.setdefault(
            a.diagram_type,
            {"count": 0, "mean_score": 0.0, "scores": [], "failures": 0, "majority": 0, "dataset": 0},
        )
        bucket["count"] += 1
        bucket["scores"].append(a.composite_score)
        if a.render_status != "success":
            bucket["failures"] += 1
        if a.majority_accepted:
            bucket["majority"] += 1
        if a.dataset_accepted:
            bucket["dataset"] += 1

    for v in by_type.values():
        scores = v.pop("scores")
        v["mean_score"] = (sum(scores) / len(scores)) if scores else None

    repairs = session.exec(select(RepairAttempt)).all()
    repair_successes = sum(1 for r in repairs if r.success)
    reviews = session.exec(select(HumanReview)).all()
    alignment = human_alignment(session)
    correlation = alignment.get("pearson_r")

    package_failures = sum(
        1 for a in artifacts if a.diagram_type == "package" and a.render_status != "success"
    )
    scores = [a.composite_score for a in artifacts]
    maj_count = sum(1 for a in artifacts if a.majority_accepted)
    ds_count = sum(1 for a in artifacts if a.dataset_accepted)
    n = len(artifacts)
    pkg_report = package_failure_report(session)
    return {
        "total_artifacts": n,
        "by_diagram_type": by_type,
        "mean_composite": (sum(scores) / len(scores)) if scores else None,
        "render_failures": sum(1 for a in artifacts if a.render_status != "success"),
        "repair_attempts": len(repairs),
        "repair_successes": repair_successes,
        "package_failure_count": package_failures,
        "package_failure_taxonomy": pkg_report.get("by_category") or {},
        "human_review_count": len(reviews),
        "human_vs_ai_correlation": correlation,
        "human_vs_ai_spearman": alignment.get("spearman_rho"),
        "human_vs_ai_n": alignment.get("n_pairs") or 0,
        "majority_accepted_count": maj_count,
        "dataset_accepted_count": ds_count,
        "majority_acceptance_rate": (maj_count / n) if n else None,
    }


def score_distributions(session: Session) -> dict[str, Any]:
    artifacts = session.exec(select(UMLArtifact)).all()
    composite_hist = {i: 0 for i in range(7)}
    by_type: dict[str, dict[int, int]] = {}
    for a in artifacts:
        bucket = max(0, min(6, int(round(a.composite_score))))
        composite_hist[bucket] += 1
        hist = by_type.setdefault(a.diagram_type, {i: 0 for i in range(7)})
        hist[bucket] += 1
    return {"composite": composite_hist, "by_diagram_type": by_type}


def artifacts_dataframe(session: Session) -> pd.DataFrame:
    artifacts = session.exec(select(UMLArtifact)).all()
    rows = []
    for a in artifacts:
        rows.append(
            {
                "id": a.id,
                "diagram_type": a.diagram_type,
                "input_mode": a.input_mode,
                "source_language": a.source_language,
                "source_requirement": a.source_requirement,
                "technical_spec": a.technical_spec,
                "uml_code": a.plantuml_code,
                "render_status": a.render_status,
                "image_path": a.image_path,
                "scores": a.composite_score,
                "majority_accepted": a.majority_accepted,
                "affirmative_votes": a.affirmative_votes,
                "dataset_accepted": a.dataset_accepted,
                "used_cot": a.used_cot,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )
    return pd.DataFrame(rows)


def export_dataset(session: Session, fmt: str = "jsonl") -> tuple[bytes, str, str]:
    df = artifacts_dataframe(session)
    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8"), "text/csv", "uml_dataset.csv"
    if fmt == "parquet":
        path = Path("/tmp/uml_export.parquet")
        df.to_parquet(path, index=False)
        return path.read_bytes(), "application/octet-stream", "uml_dataset.parquet"
    # jsonl default
    records = df.to_dict(orient="records")
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + ("\n" if records else "")
    return body.encode("utf-8"), "application/x-ndjson", "uml_dataset.jsonl"


def get_or_create_reviewer(session: Session, name: str, role: str) -> Reviewer:
    existing = session.exec(select(Reviewer).where(Reviewer.name == name)).first()
    if existing:
        if existing.role != role:
            existing.role = role
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing
    reviewer = Reviewer(name=name, role=role)
    session.add(reviewer)
    session.commit()
    session.refresh(reviewer)
    return reviewer
