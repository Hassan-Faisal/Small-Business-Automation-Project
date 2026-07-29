
from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.data.tiffin_seed import seed_tiffin_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed missing tiffin catalog records without overwriting existing data.")
    parser.parse_args()

    engine_kwargs: dict[str, object] = {"echo": False}
    if settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = SessionLocal()
    try:
        seed_tiffin_catalog(session)
    finally:
        session.close()
        engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
