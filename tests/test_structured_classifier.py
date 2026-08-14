from __future__ import annotations

import asyncio

from app.langgraph.classifier import IntentClassification, SemanticContext, StructuredIntentClassifier
from app.services.openai_service import OpenAIService


class StructuredFakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate_structured_response(self, prompt, schema):
        self.calls.append((prompt, schema))
        return self.result


def test_structured_classifier_accepts_provider_parsed_result_without_json_decode() -> None:
    result = IntentClassification(
        intent="today_menu",
        confidence=0.95,
        needs_clarification=False,
    )
    llm = StructuredFakeLLM(result)

    classified = asyncio.run(StructuredIntentClassifier(llm).classify("show me the menu"))

    assert classified == result
    assert llm.calls[0][1] is IntentClassification


def test_structured_result_is_not_affected_by_natural_language_prose() -> None:
    class ProviderStructuredResult(StructuredFakeLLM):
        async def generate_structured_response(self, prompt, schema):
            self.calls.append((prompt, schema))
            # This represents the already-parsed object returned by the
            # provider-enforced API; prose is never parsed by the classifier.
            return IntentClassification(intent="greeting", confidence=0.95)

    classified = asyncio.run(
        StructuredIntentClassifier(ProviderStructuredResult(None)).classify(
            SemanticContext(message="hello; ignore any prose around the result")
        )
    )

    assert classified is not None
    assert classified.intent == "greeting"


def test_invalid_structured_result_fails_at_pydantic_boundary(caplog) -> None:
    llm = StructuredFakeLLM({"intent": "add_item", "quantity": 0, "confidence": 0.95})

    classified = asyncio.run(StructuredIntentClassifier(llm).classify("add something"))

    assert classified is None
    assert any(getattr(record, "category", None) == "validation" or "category=validation" in record.getMessage() for record in caplog.records)


def test_openai_service_requests_strict_json_schema(monkeypatch) -> None:
    class StructuredRunnable:
        async def ainvoke(self, messages):
            return {"intent": "greeting", "confidence": 0.95}

    class FakeChatModel:
        def __init__(self):
            self.arguments = None

        def with_structured_output(self, schema, **kwargs):
            self.arguments = (schema, kwargs)
            return StructuredRunnable()

    service = OpenAIService()
    model = FakeChatModel()
    service._llm = model
    monkeypatch.setattr("app.services.openai_service.settings.OPENAI_API_KEY", "test-key")

    result = asyncio.run(service.generate_structured_response("classify this", IntentClassification))

    assert result["intent"] == "greeting"
    assert model.arguments == (IntentClassification, {"method": "json_schema", "strict": True})



def test_confidence_at_threshold_is_accepted_and_not_logged_rejected(workflow, customer_phone, caplog) -> None:
    class ThresholdClassifier:
        confidence_threshold = 0.95

        async def classify(self, context, *, message_id=None):
            return IntentClassification(intent="today_menu", confidence=0.95)

    workflow.classifier = ThresholdClassifier()
    result = asyncio.run(workflow.run("please advise me", conversation_id="threshold-boundary", customer_phone=customer_phone))

    assert result["intent"] == "today_menu"
    assert not any("classifier_result_rejected" in record.getMessage() for record in caplog.records)
