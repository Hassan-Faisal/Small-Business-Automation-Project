from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class TextSplitter:
    """
    Splits documents into smaller chunks for embedding.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """
        Split documents into chunks.
        """
        return self.text_splitter.split_documents(documents)