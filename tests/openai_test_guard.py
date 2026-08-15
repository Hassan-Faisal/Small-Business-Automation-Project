from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class RealOpenAIAccessError(AssertionError):
    """Raised when a normal test attempts to use a real OpenAI boundary."""


@dataclass
class OpenAITestGuardState:
    provider_constructions: int = 0
    provider_invocations: int = 0


STATE = OpenAITestGuardState()


def _blocked_provider(*args: Any, **kwargs: Any) -> Any:
    STATE.provider_constructions += 1
    raise RealOpenAIAccessError(
        "Real OpenAI access is disabled during the standard test suite. "
        "Use an explicit integration-test opt-in for provider tests."
    )


def _blocked_build_llm(*args: Any, **kwargs: Any) -> Any:
    STATE.provider_constructions += 1
    raise RealOpenAIAccessError(
        "Real OpenAI access is disabled during the standard test suite. "
        "build_llm() must not be reached by normal tests."
    )


class OfflineClassifier:
    """Deterministic no-provider classifier used by shared test workflows."""

    confidence_threshold = 0.78

    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, context: Any, *, message_id: str | None = None) -> None:
        self.calls += 1
        return None


def install_openai_guard() -> None:
    """Block provider construction and replace test-time embeddings."""
    import app.core.llm as llm_module
    import langchain_openai
    import app.langgraph.classifier as classifier_module
    import app.langgraph.workflow as workflow_module
    import app.rag.embeddings as embeddings_module
    import app.services.chat_service as chat_service_module
    import app.services.openai_service as service_module

    langchain_openai.ChatOpenAI = _blocked_provider  # type: ignore[assignment]
    langchain_openai.OpenAIEmbeddings = _blocked_provider  # type: ignore[assignment]
    llm_module.ChatOpenAI = _blocked_provider  # type: ignore[assignment]
    llm_module.build_llm = _blocked_build_llm  # type: ignore[assignment]
    service_module.build_llm = _blocked_build_llm  # type: ignore[assignment]
    embeddings_module.OpenAIEmbeddings = _blocked_provider  # type: ignore[assignment]
    embeddings_module.embeddings = embeddings_module._DeterministicEmbeddings()

    production_classifier = classifier_module.StructuredIntentClassifier

    class GuardedProductionClassifier(production_classifier):  # type: ignore[misc,valid-type]
        def __init__(self, llm: Any = None) -> None:
            if llm is None:
                raise RealOpenAIAccessError(
                    "Real StructuredIntentClassifier construction is disabled "
                    "during the standard test suite. Inject an offline classifier."
                )
            super().__init__(llm=llm)

    classifier_module.StructuredIntentClassifier = GuardedProductionClassifier  # type: ignore[assignment]
    workflow_module.StructuredIntentClassifier = GuardedProductionClassifier  # type: ignore[assignment]

    original_workflow = chat_service_module.OrderConversationWorkflow

    def offline_workflow(*args: Any, classifier: Any = None, **kwargs: Any) -> Any:
        return original_workflow(*args, classifier=classifier or OfflineClassifier(), **kwargs)

    chat_service_module.OrderConversationWorkflow = offline_workflow  # type: ignore[assignment]


def reset_guard_state() -> None:
    STATE.provider_constructions = 0
    STATE.provider_invocations = 0
