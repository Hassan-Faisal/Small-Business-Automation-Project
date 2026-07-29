from app.core.logging import setup_logger
from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitter
from app.rag.vector_store import VectorStore

logger = setup_logger(__name__)


class KnowledgeManager:
    """
    Coordinates the complete knowledge base lifecycle.

    Responsibilities:
    - Load an existing vector database if available.
    - Otherwise, build a new vector database from the knowledge base.
    - Provide access to the retriever for semantic search.
    """

    def __init__(self):
        self.loader = DocumentLoader()
        self.splitter = TextSplitter()
        self.vector_store = VectorStore()

    def initialize(self) -> None:
        """
        Initialize the knowledge base.

        If a persistent vector database already exists,
        load it. Otherwise, create it from the knowledge base.
        """

        if self.vector_store.exists():
            logger.info("Loading existing vector database...")

            self.vector_store.load()

            logger.info("Vector database loaded successfully.")
            return

        logger.info("No vector database found. Creating a new one...")

        documents = self.loader.load_documents()

        chunks = self.splitter.split_documents(documents)

        self.vector_store.create(chunks)

        logger.info("Vector database created successfully.")

    def get_retriever(self):
        """
        Return the retriever for semantic search.

        The knowledge base must be initialized before
        calling this method.
        """
        return self.vector_store.get_retriever()