"""Benchmark-only reachability probe derived from the production workflow.

This module deliberately does not alter production routing.  It mirrors the
workflow's deterministic gates so the harness can avoid charging a provider
for cases that production would normally resolve locally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evaluation.schema import EvaluationCase
from app.langgraph.parsing import (
    extract_position_reference,
    extract_quantity,
    extract_search_constraints,
    infer_intent,
    normalize_text,
)


@dataclass(frozen=True)
class RouteAssessment:
    production_route: str
    classifier_expected_to_be_invoked: bool
    deterministic_shortcut: bool
    deterministic_safe: bool = True
    safety_warning: str | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_route": self.production_route,
            "classifier_expected_to_be_invoked": self.classifier_expected_to_be_invoked,
            "deterministic_shortcut": self.deterministic_shortcut,
            "deterministic_safe": self.deterministic_safe,
            "safety_warning": self.safety_warning,
            "reason": self.reason,
        }


_SEMANTIC_INTENTS = {"add_item", "remove_item", "change_quantity", "search_menu", "clear_cart"}
_CONTROL_INTENTS = {
    "greeting", "today_menu", "weekly_menu", "breakfast_menu", "lunch_menu", "dinner_menu",
    "view_cart", "order_confirmation", "track_order", "delivery_area", "delivery_timing",
    "payment_methods", "subscription_plans", "subscription_status", "pause_subscription",
    "resume_subscription", "cancel_subscription", "create_subscription", "skip_meal", "bulk_order", "cancel_order", "modify_order", "provide_address", "confirm_order", "human_handoff", "faq", 
}
_QUANTITY_MARKERS = ("make", "set", "change", "kar do", "only", "actually", "just")
_REMOVAL_MARKERS = {"remove", "delete", "hata", "nikal"}
_ADD_MARKERS = ("kar do", "chahiye", "bhej", "dena", "add", "order")
_NEGATED_ADD_MARKERS = ("what", "which", "available", "kya", "dikhao", "batao")
_KNOWN_PRODUCTS = (
    "aloo paratha with raita", "chicken biryani", "daal chawal", "chicken karahi",
    "chicken qorma", "chicken pulao", "chicken handi", "seekh kabab with paratha",
    "mixed vegetable curry",
)


def _looks_like_quantity_change(message: str) -> bool:
    normalized = normalize_text(message)
    return extract_quantity(normalized) is not None and any(marker in normalized for marker in _QUANTITY_MARKERS)


def _looks_like_removal(message: str) -> bool:
    normalized = normalize_text(message)
    return any(marker in normalized.split() for marker in _REMOVAL_MARKERS) or "take out" in normalized


def _looks_like_add(message: str, deterministic_intent: str) -> bool:
    normalized = normalize_text(message)
    if deterministic_intent == "add_item":
        return True
    return any(marker in normalized for marker in _ADD_MARKERS) and not any(marker in normalized for marker in _NEGATED_ADD_MARKERS)


def _unique_product_mentioned(message: str, context: dict[str, Any]) -> bool:
    candidates = context.get("catalog_candidates") or []
    names = [str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in candidates]
    names.extend(_KNOWN_PRODUCTS)
    normalized = normalize_text(message)
    tokens = set(normalized.split())
    matches = []
    for name in names:
        if not name:
            continue
        product_tokens = {token for token in normalize_text(name).split() if token not in {"with", "and", "the"}}
        if product_tokens and product_tokens.issubset(tokens):
            matches.append(name.lower())
    if not matches:
        return False
    longest = max(len(item.split()) for item in matches)
    return len({item for item in matches if len(item.split()) == longest}) == 1


def assess_case(case: EvaluationCase) -> RouteAssessment:
    """Return the route production currently expects for one benchmark case."""
    message = case.message
    context = case.context
    deterministic_intent = infer_intent(message)
    cart = [item for item in context.get("cart", []) if isinstance(item, dict)]
    pending = context.get("pending_options") or []
    pending_action = context.get("pending_action")
    normalized = normalize_text(message)

    # The workflow consumes numeric/ordinal/demonstrative replies locally when
    # pending options are present.  A selected option is also deterministic.
    if pending and (pending_action is None or pending_action in {"add_item", "search_menu", "menu"}):
        position = extract_position_reference(message)
        selected = position is not None and 1 <= position <= len(pending)
        demonstrative = any(token in normalized.split() for token in {"that", "this", "it", "one"})
        if selected or demonstrative or normalized.isdigit():
            return RouteAssessment("deterministic", False, True, reason="pending option selection")

    constraints = extract_search_constraints(message)
    if deterministic_intent == "search_menu" and (constraints["include_terms"] or constraints["exclude_terms"]):
        return RouteAssessment("deterministic", False, True, reason="deterministic include/exclude search")

    quantity = extract_quantity(message)
    if len(cart) == 1 and quantity is not None and _looks_like_quantity_change(message) and not _looks_like_removal(message):
        warning = None
        safe = True
        if quantity <= 0:
            warning = "production quantity shortcut may coerce zero to one"
            safe = False
        return RouteAssessment("deterministic", False, True, safe, warning, "one-cart quantity shortcut")
    if len(cart) == 1 and _looks_like_removal(message):
        return RouteAssessment("deterministic", False, True, reason="one-cart removal shortcut")
    if _looks_like_add(message, deterministic_intent) and _unique_product_mentioned(message, context):
        warning = None
        safe = True
        if quantity is not None and quantity <= 0:
            warning = "production add shortcut may coerce zero to one"
            safe = False
        return RouteAssessment("deterministic", False, True, safe, warning, "unique product add shortcut")

    if deterministic_intent in _CONTROL_INTENTS:
        return RouteAssessment("deterministic", False, False, reason="deterministic workflow/control intent")
    return RouteAssessment("semantic_classifier", True, False, reason="semantic intent deferred to classifier")
