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
    _migrate_sqlite_columns()
    _ensure_default_project()


def _migrate_sqlite_columns() -> None:
    """Add paper-alignment columns on existing SQLite DBs (create_all won't alter)."""
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        return
    engine = get_engine()
    additions = {
        "umlartifact": [
            ("majority_accepted", "BOOLEAN DEFAULT 0"),
            ("affirmative_votes", "INTEGER DEFAULT 0"),
            ("dataset_accepted", "BOOLEAN DEFAULT 0"),
            ("acceptance_tau", "FLOAT DEFAULT 4.0"),
            ("used_cot", "BOOLEAN DEFAULT 0"),
            ("input_mode", "TEXT DEFAULT 'requirement'"),
            ("source_language", "TEXT"),
        ],
        "compositescore": [
            ("majority_accepted", "BOOLEAN DEFAULT 0"),
            ("affirmative_votes", "INTEGER DEFAULT 0"),
            ("dataset_accepted", "BOOLEAN DEFAULT 0"),
            ("tau", "FLOAT DEFAULT 4.0"),
        ],
        "humanreview": [
            ("score_scale", "INTEGER DEFAULT 5"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            if not existing:
                continue
            for name, ddl in cols:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _ensure_default_project() -> None:
    from sqlmodel import select

    from app.models import Project

    with Session(get_engine()) as session:
        existing = session.exec(select(Project).where(Project.name == "UML-Pipeline")).first()
        if existing is None:
            legacy = session.exec(select(Project).where(Project.name == "Thesis Demo")).first()
            if legacy is not None:
                legacy.name = "UML-Pipeline"
                legacy.description = "Default UML-Pipeline project"
                session.add(legacy)
            else:
                session.add(Project(name="UML-Pipeline", description="Default UML-Pipeline project"))
            session.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
