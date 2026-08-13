from __future__ import annotations

import asyncio

from app.langgraph.classifier import IntentClassification, SemanticContext, StructuredIntentClassifier
from app.langgraph.parsing import normalize_text


class ContextLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate_response(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_classifier_accepts_bounded_context_and_validates_semantic_fields() -> None:
    llm = ContextLLM(
        '{"intent":"add_item","item_name":"Aloo Paratha with Raita","referenced_item":null,"quantity":2,"operation":"add","confidence":0.94,"needs_clarification":false}'
    )
    context = SemanticContext(
        message="2 kar do",
        recent_turns=[{"role": "user", "content": "Aloo Paratha with Raita add kar do"}],
        cart_items=[{"name": "Aloo Paratha with Raita", "quantity": 1}],
        pending_options=[{"name": "Aloo Paratha with Raita"}],
        catalog_items=[{"name": "Aloo Paratha with Raita"}],
        active_order={"order_status": "pending"},
    )
    result = asyncio.run(StructuredIntentClassifier(llm).classify(context))
    assert result is not None
    assert result.item_name == "Aloo Paratha with Raita"
    assert result.quantity == 2
    assert result.needs_clarification is False
    assert '"recent_turns"' in llm.prompts[0]
    assert '"cart_items"' in llm.prompts[0]
    assert '"pending_options"' in llm.prompts[0]


class SemanticWorkflowStub:
    confidence_threshold = 0.78

    def __init__(self) -> None:
        self.contexts: list[SemanticContext] = []

    async def classify(self, context: SemanticContext) -> IntentClassification:
        self.contexts.append(context)
        message = normalize_text(context.message)
        if message == "2 kar do":
            return IntentClassification(intent="change_quantity", quantity=2, confidence=0.95)
        if "hata" in message or "remove" in message:
            return IntentClassification(intent="remove_item", operation="remove", confidence=0.95)
        if "wohi" in message:
            items = context.cart_items
            if len(items) == 1:
                return IntentClassification(intent="add_item", item_name=str(items[0]["name"]), operation="add", confidence=0.95)
            return IntentClassification(intent="add_item", needs_clarification=True, confidence=0.95)
        if "chicken" in message and ("remove" in message or "hata" in message):
            return IntentClassification(intent="remove_item", item_name="Chicken", operation="remove", confidence=0.95)
        if "karahi" in message:
            return IntentClassification(intent="add_item", item_name="Chicken Karahi", operation="add", confidence=0.95)
        if "biryani" in message:
            return IntentClassification(intent="add_item", item_name="Chicken Biryani", operation="add", confidence=0.95)
        return IntentClassification(intent="add_item", item_name="Aloo Paratha with Raita", operation="add", confidence=0.95)


def run(workflow, message: str, conversation_id: str, customer_phone: str):
    return asyncio.run(workflow.run(message, conversation_id=conversation_id, customer_phone=customer_phone))


def test_semantically_equivalent_food_requests_use_structured_entity(workflow, customer_phone) -> None:
    messages = [
        "Aloo Paratha with Raita add kar do",
        "Aloo Paratha Raita ke sath add kar do",
        "raita wala aloo paratha add kar do",
        "mujhe aloo paratha with raita chahiye",
    ]
    stub = SemanticWorkflowStub()
    workflow.classifier = stub  # type: ignore[assignment]
    for index, message in enumerate(messages):
        result = run(workflow, message, f"semantic-equivalent-{index}", customer_phone)
        assert result["intent"] == "add_item"
        assert result["cart"][0]["name"] == "Aloo Paratha with Raita"
    assert all(isinstance(context, SemanticContext) for context in stub.contexts)


def test_contextual_quantity_change_uses_current_cart(workflow, customer_phone) -> None:
    stub = SemanticWorkflowStub()
    workflow.classifier = stub  # type: ignore[assignment]
    run(workflow, "Aloo Paratha with Raita add kar do", "semantic-quantity", customer_phone)
    result = run(workflow, "2 kar do", "semantic-quantity", customer_phone)
    assert result["intent"] == "change_quantity"
    assert result["cart"][0]["quantity"] == 2
    assert stub.contexts[-1].cart_items[0]["name"] == "Aloo Paratha with Raita"


def test_menu_selection_and_contextual_remove_and_readd(workflow, customer_phone) -> None:
    stub = SemanticWorkflowStub()
    workflow.classifier = stub  # type: ignore[assignment]
    menu = run(workflow, "show today's menu", "semantic-menu-selection", customer_phone)
    assert menu["intent"] == "today_menu"
    selected = run(workflow, "first one add kar do", "semantic-menu-selection", customer_phone)
    assert selected["intent"] == "add_item"
    removed = run(workflow, "actually hata do", "semantic-menu-selection", customer_phone)
    assert removed["intent"] == "remove_item"
    assert removed["cart"] == []
    run(workflow, "Aloo Paratha with Raita add kar do", "semantic-reference", customer_phone)
    readded = run(workflow, "wohi add kar do", "semantic-reference", customer_phone)
    assert readded["intent"] == "add_item"
    assert readded["cart"][0]["name"] == "Aloo Paratha with Raita"


def test_ambiguous_semantic_product_reference_requires_clarification(workflow, customer_phone) -> None:
    stub = SemanticWorkflowStub()
    workflow.classifier = stub  # type: ignore[assignment]
    run(workflow, "Add 1 Chicken Karahi", "semantic-ambiguous", customer_phone)
    run(workflow, "Add 1 Chicken Biryani", "semantic-ambiguous", customer_phone)
    result = run(workflow, "remove chicken from my cart", "semantic-ambiguous", customer_phone)
    assert result["intent"] == "remove_item"
    assert len(result["cart"]) == 2
    assert "more than one" in result["response"].lower() or "which" in result["response"].lower()


def test_roman_urdu_semantics_do_not_depend_on_parser_variants(workflow, customer_phone) -> None:
    stub = SemanticWorkflowStub()
    workflow.classifier = stub  # type: ignore[assignment]
    for index, message in enumerate(("mujhe aloo paratha with raita chahiye", "raita wala aloo paratha add kar do")):
        result = run(workflow, message, f"semantic-roman-{index}", customer_phone)
        assert result["cart"][0]["name"] == "Aloo Paratha with Raita"





