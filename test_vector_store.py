from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.rag.text_splitter import TextSplitter
from app.rag.vector_store import VectorStore


@pytest.fixture()
def sample_documents() -> list[Document]:
    return [
        Document(page_content="Burger with fries", metadata={"source": "menu.md"}),
        Document(page_content="Delivery takes 30 minutes", metadata={"source": "policies.md"}),
    ]


@pytest.fixture()
def temp_vector_store(tmp_path: Path) -> VectorStore:
    store = VectorStore()
    store.persist_directory = tmp_path / "chroma"
    return store


def test_text_splitter_produces_chunks(sample_documents: list[Document]) -> None:
    splitter = TextSplitter()

    chunks = splitter.split_documents(sample_documents)

    assert len(chunks) >= 2
    assert any("Burger" in chunk.page_content for chunk in chunks)
    assert any("Delivery" in chunk.page_content for chunk in chunks)


def test_vector_store_create_load_and_retriever(temp_vector_store: VectorStore, sample_documents: list[Document]) -> None:
    assert temp_vector_store.exists() is False

    db = temp_vector_store.create(sample_documents)

    assert temp_vector_store.exists() is True
    assert db._collection.count() == len(sample_documents)

    retriever = temp_vector_store.get_retriever()
    results = retriever.invoke("delivery")

    assert results
    assert any("Delivery" in result.page_content for result in results)

    loaded = temp_vector_store.load()
    assert loaded._collection.count() == len(sample_documents)
