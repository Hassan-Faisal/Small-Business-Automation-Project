from __future__ import annotations

from threading import Lock

from app.core.logging import setup_logger
from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitter
from app.rag.vector_store import VectorStore

logger = setup_logger(__name__)


class KnowledgeManagerUnavailableError(RuntimeError):
    """Raised when the knowledge base cannot be initialized."""


class KnowledgeManager:
    """Coordinates the knowledge base lifecycle without blocking application startup."""

    def __init__(self):
        self.loader = DocumentLoader()
        self.splitter = TextSplitter()
        self.vector_store = VectorStore()
        self._initialized = False
        self._initialization_attempted = False
        self._initialization_error: Exception | None = None
        self._lock = Lock()

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            if self._initialization_attempted and self._initialization_error is not None:
                raise KnowledgeManagerUnavailableError("RAG knowledge base is unavailable.") from self._initialization_error

            self._initialization_attempted = True

            try:
                if self.vector_store.exists():
                    logger.info(
                        "knowledge_manager_vector_store_load_begin",
                        extra={"event": "knowledge_manager_vector_store_load_begin"},
                    )
                    self.vector_store.load()
                    self._initialized = True
                    logger.info(
                        "knowledge_manager_vector_store_load_complete",
                        extra={"event": "knowledge_manager_vector_store_load_complete"},
                    )
                    return

                logger.info(
                    "knowledge_manager_vector_store_build_begin",
                    extra={"event": "knowledge_manager_vector_store_build_begin"},
                )
                documents = self.loader.load_documents()
                if not documents:
                    raise RuntimeError("Knowledge base documents are missing. RAG cannot be initialized.")

                chunks = self.splitter.split_documents(documents)
                if not chunks:
                    raise RuntimeError("Knowledge base documents did not produce any chunks.")

                self.vector_store.create(chunks)
                self._initialized = True
                logger.info(
                    "knowledge_manager_vector_store_build_complete",
                    extra={"event": "knowledge_manager_vector_store_build_complete"},
                )
            except Exception as exc:
                self._initialization_error = exc
                logger.exception(
                    "knowledge_manager_initialization_failed",
                    extra={"event": "knowledge_manager_initialization_failed"},
                )
                raise KnowledgeManagerUnavailableError("RAG knowledge base is unavailable.") from exc

    def is_available(self) -> bool:
        return self._initialized

    def get_retriever(self):
        if not self._initialized:
            self.initialize()
        return self.vector_store.get_retriever()
