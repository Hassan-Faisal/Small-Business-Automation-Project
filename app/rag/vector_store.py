from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.rag.embeddings import embeddings


class VectorStore:
    """
    Handles storing and retrieving document embeddings using ChromaDB.
    """

    def __init__(self):
        self.persist_directory = Path(__file__).resolve().parents[2] / "storage" / "chroma"
        self.db: Chroma | None = None

    def exists(self) -> bool:
        """
        Check whether a persistent Chroma database exists.
        """
        return self.persist_directory.exists() and any(self.persist_directory.iterdir())

    def load(self) -> Chroma:
        """
        Load an existing persistent Chroma database.
        """
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.db = Chroma(
            persist_directory=str(self.persist_directory),
            embedding_function=embeddings,
        )
        return self.db

    def create(
        self,
        documents: list[Document],
    ) -> Chroma:
        """
        Create a persistent Chroma vector store.
        """
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.db = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=str(self.persist_directory),
        )
        return self.db

    def get_retriever(self):
        """
        Return a retriever for semantic search.
        """

        if self.db is None:
            raise RuntimeError(
                "Vector store has not been initialized. "
                "Call 'load()' or 'create()' first."
            )

        return self.db.as_retriever(search_kwargs={"k": 3})
