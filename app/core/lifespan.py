from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import check_database_connection, dispose_database_resources, get_session_factory
from app.core.logging import setup_logger
from app.rag.rag_chain import RAGChain
from app.services.chat_service import ChatService
from app.services.knowledge_manager import KnowledgeManager

logger = setup_logger(__name__)


def _require_setting(name: str, value: str | None) -> None:
    if value and str(value).strip():
        return
    raise RuntimeError(f"Missing required setting: {name}")


def _validate_startup_configuration() -> None:
    _require_setting("DATABASE_URL", settings.DATABASE_URL)
    if getattr(settings, "TWILIO_SIGNATURE_VERIFICATION_ENABLED", True):
        _require_setting("TWILIO_AUTH_TOKEN", settings.TWILIO_AUTH_TOKEN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "application_startup_begin",
        extra={"event": "application_startup_begin"},
    )
    git_sha = (
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("GIT_SHA")
        or os.getenv("COMMIT_SHA")
        or "unknown"
    )
    logger.info(
        "application_runtime_identity",
        extra={
            "event": "application_runtime_identity",
            "app_version": settings.APP_VERSION,
            "git_sha": git_sha,
            "openai_model": settings.OPENAI_MODEL,
            "openai_api_key_configured": bool(settings.OPENAI_API_KEY.strip()),
        },
    )

    logger.info(
        "application_startup_configuration_validation_begin",
        extra={"event": "application_startup_configuration_validation_begin"},
    )
    _validate_startup_configuration()
    logger.info(
        "application_startup_configuration_validation_complete",
        extra={"event": "application_startup_configuration_validation_complete"},
    )

    logger.info(
        "application_startup_database_check_begin",
        extra={"event": "application_startup_database_check_begin"},
    )
    check_database_connection()
    session_factory = get_session_factory()
    app.state.db_session_factory = session_factory
    logger.info(
        "application_startup_database_check_complete",
        extra={"event": "application_startup_database_check_complete"},
    )

    logger.info(
        "application_startup_service_construction_begin",
        extra={"event": "application_startup_service_construction_begin"},
    )
    knowledge_manager = KnowledgeManager()
    rag_chain = RAGChain(knowledge_manager=knowledge_manager)
    chat_service = ChatService(rag_chain=rag_chain, session_factory=session_factory)

    app.state.knowledge_manager = knowledge_manager
    app.state.rag_chain = rag_chain
    app.state.chat_service = chat_service
    logger.info(
        "application_startup_service_construction_complete",
        extra={"event": "application_startup_service_construction_complete"},
    )

    logger.info(
        "application_startup_completed",
        extra={"event": "application_startup_completed"},
    )

    try:
        yield
    finally:
        dispose_database_resources()
        logger.info(
            "application_shutdown_completed",
            extra={"event": "application_shutdown_completed"},
        )
