"""SQLAlchemy engine / session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.settings import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.artifact_dir.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
    return _engine


def init_db() -> None:
    from app import models  # noqa: F401 — register metadata

    SQLModel.metadata.create_all(get_engine())
    _ensure_default_project()


def _ensure_default_project() -> None:
    from sqlmodel import select

    from app.models import Project

    with Session(get_engine()) as session:
        existing = session.exec(select(Project).where(Project.name == "Thesis Demo")).first()
        if existing is None:
            session.add(Project(name="Thesis Demo", description="Default thesis demonstration project"))
            session.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
