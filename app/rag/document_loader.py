from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document


class DocumentLoader:
    """
    Loads all Markdown documents from the project's knowledge base.
    """

    def __init__(self, knowledge_base_path: str | Path | None = None):
        self.knowledge_base_path = Path(knowledge_base_path or "app/data/knowledge_base")

    def load_documents(self) -> list[Document]:
        """
        Load every Markdown document inside the knowledge base.
        """

        documents: list[Document] = []

        for file in self.knowledge_base_path.glob("*.md"):
            loader = TextLoader(file, encoding="utf-8")
            documents.extend(loader.load())

        return documents