from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal

router = APIRouter(tags=["Health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
    }


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    session_factory = getattr(request.app.state, "db_session_factory", SessionLocal)
    try:
        session = session_factory()
        try:
            session.execute(text("SELECT 1"))
        finally:
            session.close()
    except (SQLAlchemyError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return {"status": "ready"}
