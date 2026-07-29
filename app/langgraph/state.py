from __future__ import annotations

from typing import Literal

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

Intent = Literal[
    "greeting",
    "today_menu",
    "weekly_menu",
    "breakfast_menu",
    "lunch_menu",
    "dinner_menu",
    "meal_price",
    "create_subscription",
    "confirm_order",
    "update_order",
    "remove_item",
    "add_item",
    "view_cart",
    "menu",
    "delivery_area",
    "delivery_timing",
    "payment_methods",
    "faq",
    "human_escalation",
    "greeting",
    "fallback",
    "pause_subscription",
    "resume_subscription",
    "subscription_plans",
    "subscribe",
    "subscription_status",
    "skip_meal",
    "bulk_order",
    "provide_address",
    "confirm_order",
    "track_order",
    "cancel_order",
    "business_question",
]


class ConversationState(TypedDict, total=False):
    messages: list[dict[str, str]]
    intent: Intent
    last_user_message: str
    cart: list[dict[str, object]]
    address: str | None
    order_number: str | None
    order_status: str | None
    last_response: str | None
    needs_rag: bool
    conversation_id: str
    retrieved_context: str
    customer_phone: str | None
    message_id: str | None
    error: str | None
