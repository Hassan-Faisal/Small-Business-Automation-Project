from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.langgraph.parsing import extract_day, extract_order_reference, normalize_text
from app.services.openai_service import OpenAIService

ClassifierIntent = Literal[
    "greeting", "today_menu", "weekly_menu", "weekday_menu", "add_item",
    "view_cart", "remove_item", "change_quantity", "clear_cart",
    "confirm_order", "provide_address", "track_order", "cancel_order",
    "subscription_plans", "create_subscription", "subscription_status",
    "pause_subscription", "resume_subscription", "cancel_subscription",
    "skip_meal", "bulk_order", "policy_question", "faq", "delivery_area",
    "delivery_timing", "payment_methods", "human_handoff", "unknown",
]


class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: ClassifierIntent
    item_name: str | None = Field(default=None, max_length=120)
    quantity: int | None = Field(default=None, ge=1, le=50)
    day: str | None = Field(default=None, max_length=20)
    order_number: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    multiple_intents: bool = False

    @field_validator("day")
    @classmethod
    def validate_day(cls, value: str | None) -> str | None:
        if value is None:
            return None
        day = extract_day(value)
        if day is None:
            raise ValueError("day must be a valid weekday or relative day")
        return day

    @field_validator("order_number")
    @classmethod
    def validate_order_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        reference = extract_order_reference(value)
        if reference is None:
            raise ValueError("invalid order number")
        return reference


class StructuredIntentClassifier:
    """Constrained language understanding used only after deterministic routing."""

    confidence_threshold = 0.78

    def __init__(self, llm: OpenAIService | None = None) -> None:
        self.llm = llm or OpenAIService()

    @staticmethod
    def build_prompt(message: str) -> str:
        return f"""Classify this TiffinAI customer message into exactly one supported intent.
Return JSON only. Do not include markdown or explanations.

Supported intents: greeting, today_menu, weekly_menu, weekday_menu, add_item,
view_cart, remove_item, change_quantity, clear_cart, confirm_order,
provide_address, track_order, cancel_order, subscription_plans,
create_subscription, subscription_status, pause_subscription,
resume_subscription, cancel_subscription, skip_meal, bulk_order,
policy_question, delivery_area, delivery_timing, payment_methods,
human_handoff, unknown.

Rules:
- Extract only item name, quantity, day, order number, and address when present.
- Ignore prices, database IDs, availability claims, and order status claims.
- Use multiple_intents=true for requests asking for more than one action.
- Use unknown and low confidence when unclear.
- Never decide prices, totals, availability, ownership, or cancellation eligibility.

JSON shape:
{{"intent":"unknown","item_name":null,"quantity":null,"day":null,"order_number":null,"address":null,"confidence":0.0,"multiple_intents":false}}

Customer message: {message}
"""

    async def classify(self, message: str) -> IntentClassification | None:
        if not normalize_text(message):
            return None
        started = time.perf_counter()
        try:
            raw = await self.llm.generate_response(self.build_prompt(message))
            parsed: Any = json.loads(raw)
            result = IntentClassification.model_validate(parsed)
            if result.intent == "weekday_menu":
                result = result.model_copy(update={"intent": "today_menu"})
            if result.intent == "policy_question":
                result = result.model_copy(update={"intent": "faq"})
            return result
        except Exception:
            return None
        finally:
            # The caller logs the safe classification result and latency.
            _ = time.perf_counter() - started
