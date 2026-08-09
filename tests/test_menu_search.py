from __future__ import annotations

import asyncio

from app.langgraph.classifier import IntentClassification


def run(workflow, message: str, conversation_id: str, customer_phone: str):
    return asyncio.run(workflow.run(message, conversation_id=conversation_id, customer_phone=customer_phone))


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


def test_generic_category_search_returns_numbered_database_results(workflow, customer_phone, seeded_tiffin_catalog) -> None:
    stub = install_classifier(workflow, IntentClassification(intent="search_menu", query="chicken", confidence=0.95))
    result = run(workflow, "show me chicken meals", "search-chicken", customer_phone)
    expected = seeded_tiffin_catalog.search_meal_offerings("chicken")
    assert stub.calls == 1
    assert result["intent"] == "search_menu"
    assert len(expected) > 1
    for index, item in enumerate(expected, start=1):
        assert f"{index}. {item.name}" in result["response"]
        assert f"Rs. {item.price:.2f}" in result["response"]


def test_single_result_search_respects_day_and_meal_period(workflow, customer_phone, seeded_tiffin_catalog) -> None:
    stub = install_classifier(workflow, IntentClassification(
        intent="search_menu", query="halwa", day="Tuesday", meal_type="breakfast", confidence=0.95,
    ))
    result = run(workflow, "Tuesday breakfast mein halwa kya hai?", "search-one", customer_phone)
    expected = seeded_tiffin_catalog.search_meal_offerings("halwa", day_of_week="Tuesday", meal_type="breakfast")
    assert stub.calls == 1
    assert len(expected) == 1
    assert expected[0].name in result["response"]
    assert f"Rs. {expected[0].price:.2f}" in result["response"]
    assert "1." in result["response"]


def test_search_zero_results_is_grounded(workflow, customer_phone) -> None:
    install_classifier(workflow, IntentClassification(intent="search_menu", query="nonexistent dish", confidence=0.95))
    result = run(workflow, "what dishes contain this term", "search-none", customer_phone)
    assert result["intent"] == "search_menu"
    assert "could not find" in result["response"].lower()
    assert result["cart"] == []


def test_roman_urdu_search_is_non_mutating(workflow, customer_phone) -> None:
    install_classifier(workflow, IntentClassification(intent="search_menu", query="chicken", confidence=0.95))
    added = run(workflow, "Add 1 Chicken Biryani", "search-roman", customer_phone)
    searched = run(workflow, "chicken mein kya hai?", "search-roman", customer_phone)
    assert searched["intent"] == "search_menu"
    assert searched["cart"] == added["cart"]
    assert "chicken" in searched["response"].lower()


def test_ambiguous_add_lists_candidates_and_number_selects_product(workflow, customer_phone) -> None:
    ambiguous = run(workflow, "mujhe chicken chahiye", "add-clarification", customer_phone)
    assert ambiguous["intent"] == "add_item"
    assert ambiguous["cart"] == []
    assert "1." in ambiguous["response"]
    assert "2." in ambiguous["response"]
    assert "rs." in ambiguous["response"].lower()

    selected = run(workflow, "1", "add-clarification", customer_phone)
    assert selected["intent"] == "add_item"
    assert len(selected["cart"]) == 1
    assert selected["cart"][0]["name"] in ambiguous["response"]


def test_invalid_add_clarification_does_not_mutate_cart(workflow, customer_phone) -> None:
    ambiguous = run(workflow, "mujhe chicken chahiye", "add-invalid", customer_phone)
    assert "1." in ambiguous["response"]
    invalid = run(workflow, "99", "add-invalid", customer_phone)
    assert invalid["cart"] == []


def test_search_candidates_are_catalog_authoritative(workflow, customer_phone, seeded_tiffin_catalog) -> None:
    install_classifier(workflow, IntentClassification(intent="search_menu", query="rice", confidence=0.95))
    result = run(workflow, "what rice dishes do you have?", "search-authority", customer_phone)
    expected = seeded_tiffin_catalog.search_meal_offerings("rice")
    assert expected
    assert result["cart"] == []
    assert all(item.name in result["response"] and f"Rs. {item.price:.2f}" in result["response"] for item in expected)


def test_pending_numeric_selection_defaults_to_one(workflow, customer_phone) -> None:
    ambiguous = run(workflow, "mujhe chicken chahiye", "selection-default", customer_phone)
    selected = run(workflow, "4", "selection-default", customer_phone)
    assert "4." in ambiguous["response"]
    assert selected["cart"]
    assert selected["cart"][0]["quantity"] == 1


def test_pending_numeric_selection_preserves_original_quantity(workflow, customer_phone) -> None:
    ambiguous = run(workflow, "mujhe 2 chicken chahiye", "selection-quantity", customer_phone)
    selected = run(workflow, "4", "selection-quantity", customer_phone)
    assert "4." in ambiguous["response"]
    assert selected["cart"]
    assert selected["cart"][0]["quantity"] == 2


def test_numeric_quantity_without_pending_clarification_is_not_disabled(workflow, customer_phone) -> None:
    result = run(workflow, "4 Chicken Karahi add kar do", "selection-direct", customer_phone)
    assert result["cart"]
    assert result["cart"][0]["quantity"] == 4


def test_pending_selection_accepts_ordinal_and_exact_name(workflow, customer_phone) -> None:
    run(workflow, "mujhe chicken chahiye", "selection-forms", customer_phone)
    ordinal = run(workflow, "first one", "selection-forms", customer_phone)
    assert ordinal["cart"][0]["quantity"] == 1

    run(workflow, "clear cart", "selection-forms", customer_phone)
    run(workflow, "mujhe chicken chahiye", "selection-name", customer_phone)
    named = run(workflow, "Chicken Karahi", "selection-name", customer_phone)
    assert named["cart"][0]["name"] == "Chicken Karahi"
    assert named["cart"][0]["quantity"] == 1


def test_pending_selection_invalid_or_out_of_range_does_not_mutate(workflow, customer_phone) -> None:
    first = run(workflow, "mujhe chicken chahiye", "selection-invalid", customer_phone)
    invalid = run(workflow, "not that", "selection-invalid", customer_phone)
    assert invalid["cart"] == first["cart"] == []
    assert "1." in invalid["response"]

    out_of_range = run(workflow, "99", "selection-invalid", customer_phone)
    assert out_of_range["cart"] == []


def test_pending_selection_is_consumed_once(workflow, customer_phone) -> None:
    run(workflow, "mujhe chicken chahiye", "selection-once", customer_phone)
    selected = run(workflow, "4", "selection-once", customer_phone)
    repeated = run(workflow, "4", "selection-once", customer_phone)
    assert selected["cart"][0]["quantity"] == 1
    assert repeated["cart"][0]["quantity"] == 1
