from __future__ import annotations

import asyncio
import logging

from app.langgraph.classifier import IntentClassification, SemanticContext, StructuredIntentClassifier


class ResponseLLM:
    def __init__(self, response: str | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    async def generate_response(self, prompt: str) -> str:
        if self.error is not None:
            raise self.error
        return self.response or ""


def _events(caplog: object, name: str) -> list[logging.LogRecord]:
    return [record for record in caplog.records if getattr(record, "event", None) == name]  # type: ignore[attr-defined]


def test_classifier_emits_bounded_context_and_completion_diagnostics(caplog) -> None:
    caplog.set_level(logging.INFO)
    classifier = StructuredIntentClassifier(ResponseLLM(
        '{"intent":"add_item","item_name":"Aloo Paratha with Raita","referenced_item":null,"quantity":2,"operation":"add","confidence":0.95,"needs_clarification":false}'
    ))
    result = asyncio.run(classifier.classify(SemanticContext(
        message="add it",
        recent_turns=[{"role": "user", "content": "Aloo Paratha with Raita"}],
        cart_items=[{"name": "Aloo Paratha with Raita", "quantity": 1}],
        pending_options=[{"name": "Aloo Paratha with Raita"}],
        catalog_items=[{"name": "Aloo Paratha with Raita"}],
        active_order={"order_status": "pending"},
    ), message_id="msg-observe"))
    assert result is not None
    started = _events(caplog, "classifier_started")[0]
    completed = _events(caplog, "classifier_completed")[0]
    assert started.message_id == "msg-observe"
    assert started.recent_turn_count == 1
    assert started.cart_item_count == 1
    assert started.pending_option_count == 1
    assert started.catalog_item_count == 1
    assert started.active_order_present is True
    assert started.model
    assert completed.intent == "add_item"
    assert completed.item_name == "Aloo Paratha with Raita"
    assert completed.quantity == 2
    assert completed.operation == "add"
    assert completed.needs_clarification is False
    assert completed.latency_ms >= 0


def test_classifier_failure_diagnostic_redacts_configured_key(caplog, monkeypatch) -> None:
    caplog.set_level(logging.WARNING)
    secret = "test-secret-key"
    from app.core.config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", secret)
    result = asyncio.run(StructuredIntentClassifier(ResponseLLM(error=RuntimeError(f"provider rejected {secret}"))).classify("hello", message_id="msg-fail"))
    assert result is None
    failed = _events(caplog, "classifier_failed")[0]
    assert failed.message_id == "msg-fail"
    assert failed.category == "unexpected"
    assert secret not in failed.safe_exception_summary
    assert "[redacted]" in failed.safe_exception_summary
    assert failed.exception_type == "RuntimeError"


def test_workflow_emits_semantic_route_context_node_and_resolution_logs(workflow, customer_phone, monkeypatch) -> None:
    from tests.test_semantic_context import SemanticWorkflowStub
    import app.langgraph.workflow as workflow_module

    events: list[dict[str, object]] = []

    def capture_info(message: str, *args: object, **kwargs: object) -> None:
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            events.append(dict(extra))

    monkeypatch.setattr(workflow_module.logger, "info", capture_info)
    workflow.classifier = SemanticWorkflowStub()  # type: ignore[assignment]
    result = asyncio.run(workflow.run(
        "Aloo Paratha Raita ke sath add kar do",
        conversation_id="observability-conversation",
        customer_phone=customer_phone,
        message_id="msg-workflow-observe",
    ))
    assert result["intent"] == "add_item"
    by_event = lambda name: [event for event in events if event.get("event") == name]
    assert by_event("semantic_route_started")
    context = by_event("semantic_context_built")[-1]
    assert context["message_id"] == "msg-workflow-observe"
    assert int(context["catalog_item_count"]) >= 1
    node = by_event("workflow_node_selected")[-1]
    assert node["intent"] == "add_item"
    assert node["node"] == "add_item"
    resolution = by_event("product_resolution")[-1]
    assert resolution["message_id"] == "msg-workflow-observe"
    assert resolution["query_source"] == "item_name"
    assert resolution["candidate_count"] == 1
    assert resolution["selected_product_name"] == "Aloo Paratha with Raita"
