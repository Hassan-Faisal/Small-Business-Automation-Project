from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.rag.domain_boundary import decide_rag_usage, is_dynamic_business_question
from app.rag.document_loader import DocumentLoader
from app.rag.rag_chain import RAGChain
from app.services.knowledge_manager import KnowledgeManager


class DummyRetriever:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self.calls: list[str] = []
        self.documents = documents or []

    def invoke(self, question: str):
        self.calls.append(question)
        return self.documents


class DummyLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_response(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "Static policy response"


def test_active_knowledge_base_has_no_electronics_terms() -> None:
    kb_path = Path('app/data/knowledge_base')
    for file in kb_path.glob('*.md'):
        text = file.read_text(encoding='utf-8').lower()
        assert 'abc electronics' not in text
        assert 'warranty' not in text
        assert 'laptop' not in text
        assert 'phone repair' not in text
        assert 'device support' not in text
        assert 'electronics' not in text


def test_document_loader_reads_tiffin_documents() -> None:
    loader = DocumentLoader()
    documents = loader.load_documents()

    assert documents
    assert any('tiffinai' in document.page_content.lower() for document in documents)
    assert any('delivery' in document.page_content.lower() for document in documents)


def test_knowledge_manager_initializes_new_documents(monkeypatch) -> None:
    manager = KnowledgeManager()
    manager.vector_store = type('VectorStoreStub', (), {'exists': lambda self: False, 'create': lambda self, chunks: setattr(self, 'chunks', list(chunks)), 'load': lambda self: None, 'get_retriever': lambda self: object()})()
    manager.loader = DocumentLoader()
    manager.splitter = type('SplitterStub', (), {'split_documents': lambda self, documents: documents})()

    manager.initialize()

    assert manager.vector_store.chunks
    assert any('TiffinAI' in chunk.page_content for chunk in manager.vector_store.chunks)


def test_rag_prompt_uses_tiffinai_context_and_policy_language() -> None:
    chain = RAGChain()
    prompt = chain.build_prompt('What are your hours?', 'Operating hours here')

    assert 'TiffinAI' in prompt
    assert 'ABC Electronics' not in prompt
    assert 'menu availability' in prompt
    assert 'live order status' in prompt


def test_policy_question_is_allowed_through_rag(monkeypatch) -> None:
    retriever = DummyRetriever([Document(page_content='Delivery hours: 9 AM to 9 PM')])
    chain = RAGChain()
    chain.retriever = retriever  # type: ignore[assignment]
    chain.llm = DummyLLM()  # type: ignore[assignment]

    async def run() -> str:
        return await chain.ask('What are your delivery hours?')

    import asyncio
    response = asyncio.run(run())

    assert response == 'Static policy response'
    assert retriever.calls == ['What are your delivery hours?']
    assert chain.llm.prompts


@pytest.mark.parametrize(
    'question',
    [
        "What is today's menu?",
        'How much is chicken biryani?',
        'Is lunch available right now?',
        'Where is my order?',
        'What subscription do I have?',
        "Can you skip tomorrow's meal for me?",
    ],
)
def test_dynamic_business_questions_are_blocked_from_rag(question: str) -> None:
    assert is_dynamic_business_question(question) is True
    assert decide_rag_usage(question).use_rag is False


@pytest.mark.parametrize(
    'question',
    [
        'What is the cancellation policy?',
        'How do meal skips work?',
        'Which payment methods do you accept?',
        'Do you provide allergen information?',
    ],
)
def test_policy_questions_are_rag_backed(question: str) -> None:
    decision = decide_rag_usage(question)
    assert decision.use_rag is True
    assert decision.reason in {'static_policy_question', 'general_policy_question'}


def test_dynamic_question_returns_safe_fallback_without_llm_call() -> None:
    retriever = DummyRetriever()
    chain = RAGChain()
    chain.retriever = retriever  # type: ignore[assignment]
    chain.llm = DummyLLM()  # type: ignore[assignment]

    import asyncio
    response = asyncio.run(chain.ask('Where is my order?'))

    assert 'live menu, order, or customer data' in response.lower()
    assert retriever.calls == []
    assert chain.llm.prompts == []
