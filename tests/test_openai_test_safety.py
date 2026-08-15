from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.langgraph.classifier import IntentClassification, StructuredIntentClassifier
from app.services.chat_service import ChatService
from tests.openai_test_guard import OfflineClassifier, RealOpenAIAccessError, STATE


def test_standard_test_guard_blocks_real_provider_construction() -> None:
    import app.core.llm as llm_module

    with pytest.raises(RealOpenAIAccessError, match="disabled during the standard test suite"):
        llm_module.build_llm()


def test_standard_test_guard_blocks_real_classifier_without_injected_double() -> None:
    with pytest.raises(RealOpenAIAccessError, match="Inject an offline classifier"):
        StructuredIntentClassifier()


def test_workflow_fixture_uses_offline_classifier(workflow) -> None:
    assert isinstance(workflow.classifier, OfflineClassifier)
    asyncio.run(workflow.run("something completely unrelated", conversation_id="offline-guard"))
    assert workflow.classifier.calls == 1
    assert STATE.provider_constructions == 0


def test_chat_service_path_injects_offline_classifier(monkeypatch, db_session) -> None:
    class DummyRAG:
        async def ask(self, message: str) -> str:
            return "offline"

    service = ChatService(rag_chain=DummyRAG(), session_factory=lambda: db_session)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    result = asyncio.run(service.chat("hello", conversation_id="chat-offline"))

    assert result
    assert STATE.provider_constructions == 0


def test_structured_classifier_coverage_uses_a_double() -> None:
    class StructuredDouble:
        async def generate_structured_response(self, prompt: str, schema: type[IntentClassification]):
            return IntentClassification(intent="greeting", confidence=0.95)

    result = asyncio.run(StructuredIntentClassifier(StructuredDouble()).classify("hello"))

    assert result is not None
    assert result.intent == "greeting"
    assert STATE.provider_constructions == 0
