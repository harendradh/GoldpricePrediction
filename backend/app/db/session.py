"""SQLAlchemy session factory · sync (FastAPI handles concurrency via threadpool)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    # SQLite + FastAPI: allow cross-thread access
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency · yields a session, ensures close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables · safe to call on startup. Use Alembic for migrations in prod."""
    from app.db.models import Base

    Base.metadata.create_all(bind=engine)
