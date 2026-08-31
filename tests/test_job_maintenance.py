"""Job maintenance helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.models import GenerationJob, Project
from app.services.job_maintenance import reap_stale_jobs


def test_reap_stale_jobs_forces_all_on_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PROVIDERS", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'reap.db'}")
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    from app.settings import get_settings
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    from app.db import get_engine, init_db

    init_db()
    engine = get_engine()
    with Session(engine) as session:
        project = Project(name="reap-test")
        session.add(project)
        session.commit()
        session.refresh(project)

        recent = GenerationJob(
            project_id=project.id, mode="single", status="running", total=1, completed=0
        )
        old = GenerationJob(
            project_id=project.id, mode="single", status="pending", total=1, completed=0
        )
        session.add(recent)
        session.add(old)
        session.commit()
        session.refresh(recent)
        session.refresh(old)
        # Age one row past the default cutoff while leaving the other fresh.
        old.updated_at = datetime.now() - timedelta(minutes=120)
        session.add(old)
        session.commit()

        # Age-filtered pass leaves the fresh running job alone.
        assert reap_stale_jobs(session, max_age_minutes=45) == 1
        session.refresh(recent)
        session.refresh(old)
        assert recent.status == "running"
        assert old.status == "failed"

        # Startup-style pass reaps every incomplete job.
        assert reap_stale_jobs(session, max_age_minutes=None) == 1
        session.refresh(recent)
        assert recent.status == "failed"
        assert "startup" in (recent.error or "").lower()

    get_settings.cache_clear()
    dbmod._engine = None
