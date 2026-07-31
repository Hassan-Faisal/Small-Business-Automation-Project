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
    "view_cart",
    "provide_address",
    "confirm_order",
    "track_order",
    "cancel_order",
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
