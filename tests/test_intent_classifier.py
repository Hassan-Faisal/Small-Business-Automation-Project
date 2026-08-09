from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.langgraph.classifier import IntentClassification, StructuredIntentClassifier
from app.core.config import settings
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

def install_classifier(workflow, classification: IntentClassification):
    class StubClassifier:
        confidence_threshold = 0.78
        calls = 0

        async def classify(self, message: str) -> IntentClassification:
            self.calls += 1
            return classification

    stub = StubClassifier()
    workflow.classifier = stub  # type: ignore[assignment]
    return stub


def run(workflow, message: str, conversation_id: str, customer_phone: str):
    return asyncio.run(workflow.run(message, conversation_id=conversation_id, customer_phone=customer_phone))


def test_set_quantity_replaces_existing_quantity(workflow, customer_phone) -> None:
    initial = run(workflow, "Add 1 Chicken Biryani", "cart-set", customer_phone)
    assert initial["cart"][0]["quantity"] == 1
    stub = install_classifier(workflow, IntentClassification(
        intent="set_quantity", item_name="Biryani", quantity=2, confidence=0.95,
    ))
    result = run(workflow, "natural quantity update", "cart-set", customer_phone)
    assert stub.calls == 1
    assert result["cart"][0]["quantity"] == 2


def test_increment_quantity_adds_to_existing_quantity(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "cart-increment", customer_phone)
    install_classifier(workflow, IntentClassification(
        intent="increment_quantity", item_name="Biryani", quantity=2, confidence=0.95,
    ))
    result = run(workflow, "unfamiliar customer message", "cart-increment", customer_phone)
    assert result["cart"][0]["quantity"] == 4


def test_decrement_quantity_reduces_and_remove_deletes(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "cart-decrement", customer_phone)
    install_classifier(workflow, IntentClassification(
        intent="decrement_quantity", item_name="Biryani", quantity=1, confidence=0.95,
    ))
    reduced = run(workflow, "unfamiliar customer message", "cart-decrement", customer_phone)
    assert reduced["cart"][0]["quantity"] == 1

    install_classifier(workflow, IntentClassification(
        intent="remove_item", item_name="Biryani", confidence=0.95,
    ))
    removed = run(workflow, "natural removal request", "cart-decrement", customer_phone)
    assert removed["cart"] == []


def test_cart_total_is_derived_from_current_server_cart(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "cart-total", customer_phone)
    install_classifier(workflow, IntentClassification(intent="cart_total", confidence=0.95))
    result = run(workflow, "natural total request", "cart-total", customer_phone)
    assert result["intent"] == "view_cart"
    assert "your cart total is rs. 640.00" in result["response"].lower()


def test_active_cart_context_can_render_as_current_order(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "cart-context", customer_phone)
    install_classifier(workflow, IntentClassification(intent="view_cart", confidence=0.95))
    result = run(workflow, "unfamiliar customer message", "cart-context", customer_phone)
    assert result["intent"] == "view_cart"
    assert "chicken biryani" in result["response"].lower()


def test_product_resolver_handles_general_inflection_and_spelling_variation(seeded_products) -> None:
    service = seeded_products["service"]
    assert [product.name for product in service.resolve_available_products("pizzas")] == ["Pizza"]
    assert [product.name for product in service.resolve_available_products("burgers")] == ["Burger"]
    assert [product.name for product in service.resolve_available_products("friez")] == ["Fries"]


def test_product_resolver_returns_ambiguity_without_guessing(workflow) -> None:
    matches = workflow.product_service.resolve_available_products("chicken")
    assert len(matches) > 1


def test_fuzzy_resolver_handles_inflected_tiffin_product_name(workflow) -> None:
    matches = workflow.product_service.resolve_available_products("qormay")
    assert [product.name for product in matches] == ["Chicken Qorma"]


def test_classified_checkout_uses_existing_confirmation_safety(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "classified-checkout", customer_phone)
    address = run(workflow, "House 12, Street 4, Islamabad", "classified-checkout", customer_phone)
    assert "saved your delivery address" in address["response"].lower()
    install_classifier(workflow, IntentClassification(intent="confirm_order", confidence=0.95))
    result = run(workflow, "unfamiliar completion request", "classified-checkout", customer_phone)
    assert result["order_number"].startswith("TF-")
    assert result["cart"] == []


def test_active_cart_order_language_defers_broad_parser_to_classifier(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "context-order", customer_phone)
    stub = install_classifier(workflow, IntentClassification(intent="view_cart", confidence=0.95))
    result = run(workflow, "abhi mere order main kia hai?", "context-order", customer_phone)
    assert stub.calls == 1
    assert result["intent"] == "view_cart"
    assert "chicken biryani" in result["response"].lower()


def test_explicit_roman_urdu_removal_quantity_decrements(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "roman-decrement", customer_phone)
    install_classifier(workflow, IntentClassification(intent="remove_item", item_name="biryani", quantity=1, confidence=0.95))
    result = run(workflow, "ek biryani hata do", "roman-decrement", customer_phone)
    assert result["intent"] in {"remove_item", "change_quantity"}
    assert result["cart"][0]["quantity"] == 1


def test_active_cart_completion_language_uses_checkout_workflow(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "context-checkout", customer_phone)
    stub = install_classifier(workflow, IntentClassification(intent="confirm_order", confidence=0.95))
    result = run(workflow, "bas itna hi order kar dain", "context-checkout", customer_phone)
    assert stub.calls == 1
    assert result["intent"] == "confirm_order"
    assert "delivery address" in result["response"].lower()
    assert result["cart"][0]["quantity"] == 1


def test_full_conversational_cart_regression(workflow, customer_phone) -> None:
    conversation_id = "multi-turn-commerce"
    menu = run(workflow, "show today's menu", conversation_id, customer_phone)
    assert menu["intent"] == "today_menu"

    added_biryani = run(workflow, "add one Chicken Biryani", conversation_id, customer_phone)
    assert [(item["name"], item["quantity"]) for item in added_biryani["cart"]] == [("Chicken Biryani", 1)]

    class ConversationClassifier:
        confidence_threshold = 0.78
        calls = 0

        async def classify(self, message: str) -> IntentClassification:
            self.calls += 1
            normalized = message.lower()
            if "qorma" in normalized or "qorm" in normalized:
                return IntentClassification(intent="add_item", item_name="qormay", quantity=2, confidence=0.95)
            if "order main" in normalized or "order mai" in normalized:
                return IntentClassification(intent="view_cart", confidence=0.95)
            if "hata" in normalized or "remove" in normalized:
                return IntentClassification(intent="remove_item", item_name="biryani", quantity=1, confidence=0.95)
            if "make" in normalized:
                return IntentClassification(intent="set_quantity", item_name="biryani", quantity=2, confidence=0.95)
            if "total" in normalized:
                return IntentClassification(intent="cart_total", confidence=0.95)
            return IntentClassification(intent="confirm_order", confidence=0.95)

    classifier = ConversationClassifier()
    workflow.classifier = classifier  # type: ignore[assignment]
    added_qorma = run(workflow, "do qormay bhi kr dain", conversation_id, customer_phone)
    assert sorted((item["name"], item["quantity"]) for item in added_qorma["cart"]) == [
        ("Chicken Biryani", 1),
        ("Chicken Qorma", 2),
    ]

    viewed = run(workflow, "mery order mai kia kuch hai?", conversation_id, customer_phone)
    assert viewed["intent"] == "view_cart"
    assert "chicken qorma" in viewed["response"].lower()

    set_result = run(workflow, "make biryani 2", conversation_id, customer_phone)
    assert sorted((item["name"], item["quantity"]) for item in set_result["cart"]) == [
        ("Chicken Biryani", 2),
        ("Chicken Qorma", 2),
    ]

    total_before = run(workflow, "Total kitna ban raha hai?", conversation_id, customer_phone)
    expected_before = sum(Decimal(item["unit_price"]) * item["quantity"] for item in total_before["cart"])
    assert f"{expected_before:.2f}" in total_before["response"]

    decremented = run(workflow, "ek biryani hata do", conversation_id, customer_phone)
    assert sorted((item["name"], item["quantity"]) for item in decremented["cart"]) == [
        ("Chicken Biryani", 1),
        ("Chicken Qorma", 2),
    ]

    total_after = run(workflow, "Total kitna ban raha hai?", conversation_id, customer_phone)
    expected_after = sum(Decimal(item["unit_price"]) * item["quantity"] for item in total_after["cart"])
    assert f"{expected_after:.2f}" in total_after["response"]

    final_view = run(workflow, "abhi mere order main kia hai?", conversation_id, customer_phone)
    assert final_view["intent"] == "view_cart"

    checkout = run(workflow, "bas itna hi order kar dain", conversation_id, customer_phone)
    assert checkout["intent"] == "confirm_order"
    assert "delivery address" in checkout["response"].lower()
    assert checkout["cart"] == decremented["cart"]


def test_decrement_larger_than_quantity_removes_line_safely(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "decrement-large", customer_phone)
    install_classifier(workflow, IntentClassification(
        intent="decrement_quantity", item_name="biryani", quantity=5, confidence=0.95,
    ))
    result = run(workflow, "unfamiliar decrement request", "decrement-large", customer_phone)
    assert result["cart"] == []


def test_remove_without_explicit_quantity_removes_entire_line(workflow, customer_phone) -> None:
    run(workflow, "Add 2 Chicken Biryani", "remove-line", customer_phone)
    result = run(workflow, "remove Chicken Biryani", "remove-line", customer_phone)
    assert result["cart"] == []


def test_add_item_explicit_message_quantity_overrides_classifier_quantity(workflow, customer_phone) -> None:
    stub = install_classifier(workflow, IntentClassification(
        intent="add_item", item_name="qormay", quantity=1, confidence=0.95,
    ))
    result = run(workflow, "do qormay bhi kr dain", "add-quantity-roman", customer_phone)
    assert stub.calls == 1
    assert [(item["name"], item["quantity"]) for item in result["cart"]] == [("Chicken Qorma", 2)]


def test_numeric_and_number_word_add_quantities(workflow, customer_phone) -> None:
    numeric = run(workflow, "3 Chicken Qorma add karo", "add-quantity-numeric", customer_phone)
    assert numeric["cart"][0]["quantity"] == 3
    word = run(workflow, "mujhe do Chicken Qorma chahiye", "add-quantity-word", customer_phone)
    assert word["cart"][0]["quantity"] == 2


def test_recent_cart_survives_greeting(workflow, customer_phone, monkeypatch) -> None:
    monkeypatch.setattr(settings, "CART_INACTIVITY_MINUTES", 1440)
    run(workflow, "Add 1 Chicken Biryani", "recent-cart", customer_phone)
    result = run(workflow, "Salam", "recent-cart", customer_phone)
    assert result["cart"][0]["name"] == "Chicken Biryani"


def test_expired_cart_is_cleared_without_touching_state_history(workflow, customer_phone, monkeypatch) -> None:
    monkeypatch.setattr(settings, "CART_INACTIVITY_MINUTES", 60)
    run(workflow, "Add 1 Chicken Biryani", "expired-cart", customer_phone)
    record = workflow.memory._load_record("expired-cart")
    assert record is not None
    record.updated_at = datetime.now(timezone.utc) - timedelta(hours=3)
    workflow.product_service.db.commit()
    result = run(workflow, "Salam", "expired-cart", customer_phone)
    assert result["cart"] == []


def test_placed_order_survives_cart_expiry_and_supports_tracking(workflow, customer_phone, monkeypatch) -> None:
    run(workflow, "Add 1 Chicken Biryani", "placed-history", customer_phone)
    run(workflow, "House 12, Street 4, Islamabad", "placed-history", customer_phone)
    placed = run(workflow, "Confirm order", "placed-history", customer_phone)
    order_number = placed["order_number"]
    record = workflow.memory._load_record("placed-history")
    assert record is not None
    record.updated_at = datetime.now(timezone.utc) - timedelta(hours=3)
    workflow.product_service.db.commit()
    tracked = run(workflow, "Track my order", "placed-history", customer_phone)
    assert tracked["order_number"] == order_number
    assert tracked["cart"] == []


def test_modify_placed_order_returns_safe_customer_owned_guidance(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "modify-placed", customer_phone)
    run(workflow, "House 12, Street 4, Islamabad", "modify-placed", customer_phone)
    placed = run(workflow, "Confirm order", "modify-placed", customer_phone)
    result = run(workflow, "mujhay kuch change krna hai order mai", "modify-placed", customer_phone)
    assert result["intent"] == "modify_order"
    assert placed["order_number"] in result["response"]
    assert "cannot edit" in result["response"].lower()
    assert "cancel" in result["response"].lower()


def test_modify_non_cancellable_placed_order_does_not_offer_cancellation(workflow, customer_phone) -> None:
    run(workflow, "Add 1 Chicken Biryani", "modify-terminal", customer_phone)
    run(workflow, "House 12, Street 4, Islamabad", "modify-terminal", customer_phone)
    placed = run(workflow, "Confirm order", "modify-terminal", customer_phone)
    workflow.order_service.update_order_status(placed["order_number"], "completed")
    result = run(workflow, "change my order", "modify-terminal", customer_phone)
    assert result["intent"] == "modify_order"
    assert "cannot edit" in result["response"].lower()
    assert "cannot cancel" in result["response"].lower()
