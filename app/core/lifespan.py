from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.twilio import _get_twilio_request_validator
from app.core.config import settings
from app.core.database import build_session_factory, initialize_database
from app.core.logging import setup_logger
from app.data.tiffin_seed import seed_tiffin_catalog
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
    _require_setting("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    if getattr(settings, "TWILIO_SIGNATURE_VERIFICATION_ENABLED", True):
        _require_setting("TWILIO_AUTH_TOKEN", settings.TWILIO_AUTH_TOKEN)


def _seed_demo_catalog(session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        seed_tiffin_catalog(session)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    """

    logger.info(
        "application_startup_lifecycle_initialization",
        extra={"event": "application_startup_lifecycle_initialization"},
    )

    _validate_startup_configuration()
    initialize_database()
    db_session_factory = build_session_factory()
    _seed_demo_catalog(db_session_factory)

    app.state.db_session_factory = db_session_factory

    logger.info(
        "application_startup_database_ready",
        extra={"event": "application_startup_database_ready"},
    )

    knowledge_manager = KnowledgeManager()
    knowledge_manager.initialize()
    app.state.knowledge_manager = knowledge_manager

    logger.info(
        "application_startup_knowledge_manager_ready",
        extra={"event": "application_startup_knowledge_manager_ready"},
    )

    rag_chain = RAGChain(knowledge_manager)
    chat_service = ChatService(rag_chain, session_factory=db_session_factory)

    app.state.rag_chain = rag_chain
    app.state.chat_service = chat_service

    logger.info(
        "application_startup_chat_service_ready",
        extra={"event": "application_startup_chat_service_ready"},
    )

    if getattr(settings, "TWILIO_SIGNATURE_VERIFICATION_ENABLED", True):
        _get_twilio_request_validator()

    logger.info(
        "application_startup_completed",
        extra={"event": "application_startup_completed"},
    )

    yield

    logger.info(
        "application_shutdown_completed",
        extra={"event": "application_shutdown_completed"},
    )
