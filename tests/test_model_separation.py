from __future__ import annotations

from app.core.config import settings
from app.langgraph.classifier import StructuredIntentClassifier
from app.rag.rag_chain import RAGChain
from app.services.openai_service import OpenAIService


def _services(monkeypatch, *, default: str, classifier: str = "", rag: str = ""):
    monkeypatch.setattr(settings, "OPENAI_MODEL", default)
    monkeypatch.setattr(settings, "OPENAI_CLASSIFIER_MODEL", classifier)
    monkeypatch.setattr(settings, "OPENAI_RAG_MODEL", rag)
    classifier_service = StructuredIntentClassifier(llm=OpenAIService(model=classifier or default))
    rag_chain = RAGChain(knowledge_manager=None, llm=OpenAIService(model=rag or default))
    return classifier_service, rag_chain


def test_only_default_model_is_used_for_classifier_and_rag(monkeypatch) -> None:
    classifier, rag = _services(monkeypatch, default="default-model")

    assert classifier.llm.model == "default-model"
    assert rag.llm.model == "default-model"


def test_classifier_override_does_not_change_rag_fallback(monkeypatch) -> None:
    classifier, rag = _services(monkeypatch, default="default-model", classifier="classifier-model")

    assert classifier.llm.model == "classifier-model"
    assert rag.llm.model == "default-model"


def test_rag_override_does_not_change_classifier_fallback(monkeypatch) -> None:
    classifier, rag = _services(monkeypatch, default="default-model", rag="rag-model")

    assert classifier.llm.model == "default-model"
    assert rag.llm.model == "rag-model"


def test_classifier_and_rag_can_use_separate_models(monkeypatch) -> None:
    classifier, rag = _services(
        monkeypatch,
        default="default-model",
        classifier="classifier-model",
        rag="rag-model",
    )

    assert classifier.llm.model == "classifier-model"
    assert rag.llm.model == "rag-model"


def test_openai_service_explicit_model_is_forwarded_only_when_used(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_MODEL", "default-model")
    service = OpenAIService(model="specific-model")

    assert service.model == "specific-model"
    assert service._llm is None
