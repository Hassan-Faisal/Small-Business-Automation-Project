from __future__ import annotations

import asyncio

from app.langgraph.classifier import IntentClassification, SemanticContext


class CountingClassifier:
    allow_deterministic_shortcuts = True
    max_generations_per_message = 1
    confidence_threshold = 0.78

    def __init__(self, result: IntentClassification | None = None) -> None:
        self.calls = 0
        self.contexts: list[SemanticContext] = []
        self.result = result

    async def classify(self, context: SemanticContext, *, message_id: str | None = None):
        self.calls += 1
        self.contexts.append(context)
        return self.result


def run(workflow, message: str, conversation_id: str) -> dict[str, object]:
    return asyncio.run(workflow.run(message, conversation_id=conversation_id, customer_phone="15551234567"))


def test_explicit_menu_and_cart_commands_skip_classifier(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier

    assert run(workflow, "today menu", "cost-menu")["intent"] == "today_menu"
    assert run(workflow, "show my cart", "cost-cart")["intent"] == "view_cart"
    assert classifier.calls == 0


def test_pending_numeric_selection_skips_classifier(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier
    run(workflow, "show chicken options", "cost-pending")
    classifier.calls = 0
    workflow.memory.save(
        "cost-pending",
        messages=[
            {"role": "assistant", "content": "long rendered menu that must not be sent", "options": [{"name": "Chicken Karahi", "price": "380.00"}, {"name": "Chicken Biryani", "price": "320.00"}], "context_type": "add_item", "pending_action": "add_item"}
        ],
        cart=[],
    )

    result = run(workflow, "second one", "cost-pending")

    assert result["intent"] == "add_item"
    assert classifier.calls == 0


def test_one_cart_quantity_and_removal_are_local(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier
    run(workflow, "Add 1 Chicken Biryani", "cost-cart-ops")
    classifier.calls = 0

    changed = run(workflow, "acha 2 krdo", "cost-cart-ops")
    assert changed["cart"][0]["quantity"] == 2
    assert classifier.calls == 0

    removed = run(workflow, "remove it", "cost-cart-ops")
    assert removed["cart"] == []
    assert classifier.calls == 0


def test_unique_product_add_can_be_local_and_ambiguous_add_is_semantic(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier

    result = run(workflow, "beef kofta kar do", "cost-unique-add")
    assert result["intent"] == "add_item"
    assert classifier.calls == 0

    ambiguous = run(workflow, "add chicken", "cost-ambiguous-add")
    assert ambiguous["intent"] in {"add_item", "fallback"}
    assert classifier.calls == 1


def test_deterministic_constraints_skip_classifier(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier

    result = run(workflow, "show meals without biryani", "cost-constraints")

    assert result["intent"] == "search_menu"
    assert classifier.calls == 0


def test_ambiguous_reference_and_informal_search_remain_semantic(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier
    run(workflow, "Add 1 Chicken Karahi", "cost-hard")
    run(workflow, "Add 1 Chicken Biryani", "cost-hard")
    classifier.calls = 0

    run(workflow, "remove that one", "cost-hard")
    assert classifier.calls == 1

    classifier.calls = 0
    run(workflow, "chicken mein kuch dikhao", "cost-hard-search")
    assert classifier.calls == 1


def test_classifier_budget_is_one_call_per_message(workflow) -> None:
    classifier = CountingClassifier()
    workflow.classifier = classifier

    run(workflow, "something I cannot express clearly", "cost-budget")

    assert classifier.calls <= 1


def test_semantic_context_is_compact_and_drops_rendered_assistant_text(workflow) -> None:
    long_menu = "Friday menu: " + ("Chicken Biryani, Beef Kofta Curry, Aloo Paratha. " * 60)
    memory = {
        "messages": [
            {"role": "user", "content": "show today's menu"},
            {"role": "assistant", "content": long_menu},
            {"role": "user", "content": "beef kofta kar do"},
        ],
        "cart": [],
        "address": None,
        "order_number": None,
        "order_status": None,
    }

    context = workflow._semantic_context("beef kofta kar do", memory, profile="add_item", catalog_candidates=[{"name": "Beef Kofta Curry"}])
    recent_text = " ".join(turn["content"] for turn in context.recent_turns)

    assert long_menu not in recent_text
    assert len(context.catalog_items) <= 5
    assert not context.cart_items
    assert len(context.recent_turns) <= 2


def test_context_profiles_only_include_relevant_state(workflow) -> None:
    memory = {
        "messages": [{"role": "user", "content": "previous request"}],
        "cart": [{"name": "Chicken Biryani", "quantity": 1}],
        "order_number": "TF-1",
        "order_status": "pending",
    }

    search = workflow._semantic_context("show chicken meals", memory, profile="search_menu", catalog_candidates=[{"name": "Chicken Biryani"}])
    quantity = workflow._semantic_context("make it two", memory, profile="change_quantity")

    assert not search.cart_items
    assert not search.active_order
    assert quantity.cart_items
    assert not quantity.catalog_items
