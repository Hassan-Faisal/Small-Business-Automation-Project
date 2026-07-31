from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def _engine_kwargs(database_url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"echo": False}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    return kwargs


def build_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    resolved_database_url = database_url or settings.DATABASE_URL
    engine = create_engine(resolved_database_url, **_engine_kwargs(resolved_database_url))
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session for FastAPI dependencies.

    The session is always closed after the request is completed.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    """Apply Alembic migrations for the configured database."""
    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
