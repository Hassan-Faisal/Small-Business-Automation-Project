from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.database import check_database_connection

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
async def ready() -> dict[str, str]:
    try:
        check_database_connection()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return {"status": "ready"}
