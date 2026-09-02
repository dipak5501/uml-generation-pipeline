"""Thesis-committee briefing and frozen evaluation snapshot."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.security import require_api_access
from app.services.thesis import committee_briefing, stratified_snapshot

router = APIRouter(prefix="/api/thesis", tags=["thesis"])


@router.get("/briefing")
def briefing(session: Session = Depends(get_session)):
    """Paper vs this Mac Studio, RQs, formula, live human alignment."""
    return committee_briefing(session)


@router.get("/demo-cases")
def demo_cases(session: Session = Depends(get_session)):
    data = committee_briefing(session)
    return {"demo_cases": data["demo_cases"], "formula": data["formula"]}


@router.get("/snapshot")
def snapshot(
    fmt: str = Query(default="json"),
    seed: int = Query(default=42, ge=0, le=10_000),
    n_per_type: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_access),
):
    """Stratified take-home set (seed 42, 10 per type by default)."""
    payload = stratified_snapshot(session, seed=seed, n_per_type=n_per_type)
    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        fields = [
            "id",
            "diagram_type",
            "input_mode",
            "source_language",
            "render_status",
            "composite_score",
            "majority_accepted",
            "dataset_accepted",
            "affirmative_votes",
            "source_requirement",
            "plantuml_code",
        ]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in payload["items"]:
            writer.writerow(row)
        return Response(
            content=buf.getvalue().encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="uml_eval_snapshot.csv"'},
        )
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="uml_eval_snapshot.json"'},
    )
