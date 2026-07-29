from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import setup_logger
from app.core.config import settings
from app.rag.rag_chain import RAGChain
from app.api.routes.twilio import _get_twilio_request_validator
from app.services.chat_service import ChatService
from app.services.knowledge_manager import KnowledgeManager

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    """

    logger.info(
        "application_startup_lifecycle_initialization",
        extra={"event": "application_startup_lifecycle_initialization"},
    )

    logger.info(
        "application_startup_lifecycle_ready",
        extra={"event": "application_startup_lifecycle_ready"},
    )
    logger.info(
        "application_startup_knowledge_manager",
        extra={"event": "application_startup_knowledge_manager"},
    )

    knowledge_manager = KnowledgeManager()
    knowledge_manager.initialize()

    logger.info(
        "application_startup_knowledge_manager_ready",
        extra={"event": "application_startup_knowledge_manager_ready"},
    )

    app.state.knowledge_manager = knowledge_manager

    logger.info(
        "application_startup_rag_chain",
        extra={"event": "application_startup_rag_chain"},
    )

    rag_chain = RAGChain(knowledge_manager)

    logger.info(
        "application_startup_rag_chain_ready",
        extra={"event": "application_startup_rag_chain_ready"},
    )
    logger.info(
        "application_startup_chat_service",
        extra={"event": "application_startup_chat_service"},
    )

    chat_service = ChatService(rag_chain)

    logger.info(
        "application_startup_chat_service_ready",
        extra={"event": "application_startup_chat_service_ready"},
    )

    app.state.rag_chain = rag_chain
    app.state.chat_service = chat_service

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
