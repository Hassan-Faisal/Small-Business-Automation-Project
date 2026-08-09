from __future__ import annotations

import asyncio

from app.langgraph.classifier import IntentClassification, StructuredIntentClassifier
import app.langgraph.workflow as workflow_module


class FakeLLM:
    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.response = response or ""
        self.error = error
        self.calls = 0

    async def generate_response(self, prompt: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


def classify(response: str) -> IntentClassification | None:
    return asyncio.run(StructuredIntentClassifier(FakeLLM(response=response)).classify("unfamiliar request"))


def test_classifier_validates_entities_and_ignores_price() -> None:
    result = classify('{"intent":"add_item","item_name":"Chicken Karahi","quantity":1,"confidence":0.93}')
    assert result is not None
    assert result.intent == "add_item"
    assert result.item_name == "Chicken Karahi"
    assert result.quantity == 1


def test_classifier_normalizes_day_and_order_reference() -> None:
    result = classify('{"intent":"track_order","order_number":"ord-1234","day":"Friday","confidence":0.9}')
    assert result is not None
    assert result.order_number == "ORD-1234"
    assert result.day == "Friday"


def test_classifier_rejects_malformed_or_unsafe_entities() -> None:
    assert classify('{"intent":"add_item","quantity":0,"confidence":0.9}') is None
    assert classify('{"intent":"track_order","order_number":"someone-elses-id","confidence":0.9}') is None
    assert classify("not json") is None


def test_classifier_model_failure_is_safe() -> None:
    llm = FakeLLM(error=TimeoutError("timeout"))
    result = asyncio.run(StructuredIntentClassifier(llm).classify("where is my food"))
    assert result is None
    assert llm.calls == 1
def test_deterministic_intents_do_not_invoke_classifier(workflow, customer_phone) -> None:
    class SpyClassifier:
        confidence_threshold = 0.78
        calls = 0

        async def classify(self, message: str) -> None:
            self.calls += 1
            return None

    spy = SpyClassifier()
    workflow.classifier = spy  # type: ignore[assignment]
    result = asyncio.run(workflow.run("view cart", conversation_id="classifier-deterministic", customer_phone=customer_phone))
    assert result["intent"] == "view_cart"
    assert spy.calls == 0


def test_fallback_routes_only_validated_intent_to_existing_workflow(workflow, customer_phone) -> None:
    class StubClassifier:
        confidence_threshold = 0.78

        async def classify(self, message: str) -> IntentClassification:
            return IntentClassification(intent="add_item", item_name="Chicken Pulao", quantity=1, confidence=0.91)

    workflow.classifier = StubClassifier()  # type: ignore[assignment]
    result = asyncio.run(workflow.run("could you grab me one chicken pulao please", conversation_id="classifier-fallback", customer_phone=customer_phone))
    assert result["intent"] == "add_item"
    assert result["cart"][0]["name"] == "Chicken Pulao"


def test_multiple_intents_do_not_modify_cart(workflow, customer_phone) -> None:
    class StubClassifier:
        confidence_threshold = 0.78

        async def classify(self, message: str) -> IntentClassification:
            return IntentClassification(intent="add_item", item_name="Chicken Pulao", confidence=0.91, multiple_intents=True)

    workflow.classifier = StubClassifier()  # type: ignore[assignment]
    result = asyncio.run(workflow.run("I have two things", conversation_id="classifier-multi", customer_phone=customer_phone))
    assert result["intent"] == "fallback"
    assert result["cart"] == []
    assert "one action" in result["response"].lower()

def test_low_confidence_fallback_does_not_modify_cart(workflow, customer_phone) -> None:
    class StubClassifier:
        confidence_threshold = 0.78

        async def classify(self, message: str) -> IntentClassification:
            return IntentClassification(intent="add_item", item_name="Chicken Pulao", confidence=0.50)

    workflow.classifier = StubClassifier()  # type: ignore[assignment]
    result = asyncio.run(workflow.run("some unclear request", conversation_id="classifier-low", customer_phone=customer_phone))
    assert result["intent"] == "fallback"
    assert result["cart"] == []

def test_ambiguous_classified_product_requires_clarification(workflow, customer_phone) -> None:
    class StubClassifier:
        confidence_threshold = 0.78

        async def classify(self, message: str) -> IntentClassification:
            return IntentClassification(intent="add_item", item_name="chicken", confidence=0.91)

    workflow.classifier = StubClassifier()  # type: ignore[assignment]
    result = asyncio.run(workflow.run("chicken please", conversation_id="classifier-ambiguous", customer_phone=customer_phone))
    assert result["intent"] == "add_item"
    assert result["cart"] == []
    assert "matching meal" in result["response"].lower() or "which" in result["response"].lower()

def test_production_phrase_uses_classifier_once_and_preserves_cart(workflow, customer_phone) -> None:
    existing = asyncio.run(workflow.run("I want Chicken Karahi", conversation_id="classifier-production", customer_phone=customer_phone))
    assert existing["cart"][0]["name"] == "Chicken Karahi"

    class StubClassifier:
        confidence_threshold = 0.78
        calls = 0

        async def classify(self, message: str) -> IntentClassification:
            self.calls += 1
            return IntentClassification(intent="add_item", item_name="Chicken Pulao", quantity=1, confidence=0.95)

    stub = StubClassifier()
    workflow.classifier = stub  # type: ignore[assignment]
    result = asyncio.run(workflow.run("Chicken Pulao bhi aik kar dena", conversation_id="classifier-production", customer_phone=customer_phone))

    assert stub.calls == 1
    assert result["intent_source"] == "llm_fallback"
    assert result["intent"] == "add_item"
    assert [(item["name"], item["quantity"]) for item in result["cart"]] == [
        ("Chicken Karahi", 1),
        ("Chicken Pulao", 1),
    ]
    assert "didn't quite understand" not in result["response"].lower()

def test_one_final_classification_decision_per_turn(workflow, customer_phone, monkeypatch) -> None:
    class StubClassifier:
        confidence_threshold = 0.78

        async def classify(self, message: str) -> IntentClassification:
            return IntentClassification(intent="add_item", item_name="Chicken Pulao", quantity=1, confidence=0.95)

    events: list[dict[str, object]] = []

    def capture_info(message: str, *args: object, **kwargs: object) -> None:
        if message == "intent_classified":
            events.append(dict(kwargs.get("extra") or {}))

    monkeypatch.setattr(workflow_module.logger, "info", capture_info)
    workflow.classifier = StubClassifier()  # type: ignore[assignment]
    asyncio.run(workflow.run("Chicken Pulao bhi aik kar dena", conversation_id="classifier-one-decision", customer_phone=customer_phone))

    assert len(events) == 1
    assert events[0]["intent_source"] == "llm_fallback"