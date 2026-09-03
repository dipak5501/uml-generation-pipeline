"""Harvest accepted live artifacts for self-training top-up."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models import UMLArtifact

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "harvest_accepted_for_finetune",
    ROOT / "scripts" / "harvest_accepted_for_finetune.py",
)
assert _SPEC and _SPEC.loader
_harvest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_harvest)


def test_row_from_artifact_requires_spec_and_uml():
    a = UMLArtifact(
        project_id=1,
        diagram_type="class",
        technical_spec="x" * 50,
        plantuml_code="@startuml\nclass Foo\n@enduml",
        render_status="success",
        dataset_accepted=True,
        majority_accepted=True,
        composite_score=4.5,
    )
    row = _harvest._row_from_artifact(a, human_boost=False)
    assert row is not None
    assert row["uml_code"].startswith("@startuml")
    assert row["source_dataset"] == "live_accepted_harvest"


def test_row_rejects_failed_render():
    a = UMLArtifact(
        project_id=1,
        diagram_type="class",
        technical_spec="x" * 50,
        plantuml_code="@startuml\nclass Foo\n@enduml",
        render_status="failed",
    )
    assert _harvest._row_from_artifact(a, human_boost=False) is None


def test_fingerprint_stable():
    a = "@startuml\nclass A\n@enduml"
    b = "@startuml\n  class A  \n@enduml\n"
    assert _harvest._uml_fingerprint(a) == _harvest._uml_fingerprint(b)
