from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

Intent = Literal[
    "greeting",
    "today_menu",
    "weekly_menu",
    "breakfast_menu",
    "lunch_menu",
    "dinner_menu",
    "add_item",
    "remove_item",
    "change_quantity",
    "clear_cart",
    "view_cart",
    "search_menu",
    "provide_address",
    "confirm_order",
    "track_order",
    "cancel_order",
    "modify_order",
    "subscription_plans",
    "create_subscription",
    "subscription_status",
    "pause_subscription",
    "resume_subscription",
    "cancel_subscription",
    "skip_meal",
    "bulk_order",
    "delivery_area",
    "delivery_timing",
    "payment_methods",
    "faq",
    "human_handoff",
    "fallback",
]


class ConversationState(TypedDict, total=False):
    messages: list[dict[str, object]]
    intent: Intent
    last_user_message: str
    cart: list[dict[str, object]]
    address: str | None
    order_number: str | None
    order_status: str | None
    last_response: str | None
    conversation_id: str
    retrieved_context: str
    customer_phone: str | None
    message_id: str | None
    error: str | None
    displayed_options: list[dict[str, object]]
    displayed_context_type: str
    pending_subscription_plan: dict[str, object]
    pending_menu_option: dict[str, object]
    pending_clarification: dict[str, object] | None
    selected_menu_day: str
    classified_item_name: str | None
    classified_referenced_item: str | None
    classified_query: str | None
    classified_meal_type: str | None
    classified_quantity: int | None
    classified_day: str | None
    classified_order_number: str | None
    classified_address: str | None
    classified_include_terms: list[str]
    classified_exclude_terms: list[str]
    needs_clarification: bool
    intent_source: str
    intent_confidence: float
    clarification_response: str | None
    cart_operation: str | None
    cart_view_mode: str | None
    pending_action: str | None
    selected_menu_option: dict[str, object] | None
    llm_telemetry: dict[str, object]


