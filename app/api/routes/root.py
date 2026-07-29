from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(
    tags=["Health"],
)


@router.get("/")
async def root() -> dict[str, str]:
    """
    Health check endpoint.
    """

    return {
        "message": (
            f"{settings.APP_NAME} API is running successfully!"
        )
    }