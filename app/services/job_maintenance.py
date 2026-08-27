"""Startup / maintenance helpers for generation jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import GenerationJob

logger = logging.getLogger(__name__)


def reap_stale_jobs(
    session: Session,
    *,
    max_age_minutes: int | None = 45,
) -> int:
    """Mark long-running/pending jobs as failed so the UI does not show ghosts.

    In-process thread workers die with the API process; LaunchAgent restarts leave
    ``running`` rows that never complete. Safe to call on every API startup.

    Pass ``max_age_minutes=None`` (or ``<= 0``) to reap *every* pending/running job.
    That is the correct startup behavior: no worker from a prior process can finish.
    A positive age keeps younger rows (for optional periodic maintenance calls).
    """
    cutoff = None
    if max_age_minutes is not None and max_age_minutes > 0:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            minutes=max_age_minutes
        )
    stale = session.exec(
        select(GenerationJob).where(GenerationJob.status.in_(["running", "pending"]))
    ).all()
    n = 0
    for job in stale:
        touched = job.updated_at or job.created_at
        if touched is not None and getattr(touched, "tzinfo", None) is not None:
            touched = touched.replace(tzinfo=None)
        if cutoff is not None and touched is not None and touched > cutoff:
            continue
        prior = job.status
        job.status = "failed"
        if cutoff is None:
            reason = (
                f"Reaped orphaned {prior} job on API startup "
                "(in-process worker did not survive restart)."
            )
        else:
            reason = (
                f"Reaped stale {prior} job after {max_age_minutes}m without completion "
                "(likely API restart mid-run)."
            )
        job.error = job.error or reason
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(job)
        n += 1
    if n:
        session.commit()
        logger.warning("Reaped %s stale generation job(s)", n)
    return n
