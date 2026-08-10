from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import settings
from app.core.logging import setup_logger
from app.langgraph.parsing import extract_day, extract_order_reference, normalize_text
from app.services.openai_service import OpenAIService

logger = setup_logger(__name__)

ClassifierIntent = Literal[
    "greeting", "today_menu", "weekly_menu", "weekday_menu", "add_item",
    "view_cart", "search_menu", "cart_total", "remove_item", "set_quantity", "increment_quantity", "decrement_quantity", "change_quantity", "clear_cart",
    "confirm_order", "provide_address", "track_order", "cancel_order", "modify_order",
    "subscription_plans", "create_subscription", "subscription_status",
    "pause_subscription", "resume_subscription", "cancel_subscription",
    "skip_meal", "bulk_order", "policy_question", "faq", "delivery_area",
    "delivery_timing", "payment_methods", "human_handoff", "unknown",
]


CartOperation = Literal["add", "set", "increment", "decrement", "remove"]

class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: ClassifierIntent
    item_name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=120)
    meal_type: str | None = Field(default=None, max_length=20)
    quantity: int | None = Field(default=None, ge=1, le=50)
    operation: CartOperation | None = None
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
view_cart, search_menu, cart_total, remove_item, set_quantity, increment_quantity, decrement_quantity, change_quantity, clear_cart, confirm_order,
provide_address, track_order, cancel_order, modify_order, subscription_plans,
create_subscription, subscription_status, pause_subscription,
resume_subscription, cancel_subscription, skip_meal, bulk_order,
policy_question, delivery_area, delivery_timing, payment_methods,
human_handoff, unknown.

Rules:
- Extract only item name, search query, quantity, meal period, day, order number, and address when present.
- Ignore prices, database IDs, availability claims, and order status claims.
- Use multiple_intents=true only when the customer genuinely requests more than one separate action.
- Use unknown and low confidence when the message is genuinely unclear.
- Never decide prices, totals, availability, ownership, or cancellation eligibility.

Intent rules:
- Use add_item when the customer expresses an intention to order, get, take, buy, add, or have a food item.
- For add_item:
  - put the food name in item_name.
  - extract quantity when stated.
  - set operation="add".
  - query should normally be null.
- Use search_menu only when the customer is asking for information about a food item, such as whether it exists, is available, what it costs, or asking to find/search for it.
- For search_menu:
  - put the food being searched for in query.
  - do not interpret a purchase request as search_menu.
- Words such as "order", "want", "get me", "give me", "add", "I'll have", "I need", and "can I get" normally indicate add_item when they refer to food.
- Questions such as "how much is", "do you have", "is available", "find", and "what meals have" normally indicate search_menu.
- A customer does not need to use the word "order" for add_item.
- "I want 2 Chicken Karahi" is add_item, not search_menu.
- "Order 2 Chicken Karahi" is add_item, not search_menu.
- "Give me 2 Chicken Karahi" is add_item, not search_menu.
- "I need Chicken Karahi" is add_item, not search_menu.
- "How much is Chicken Karahi?" is search_menu.
- "Is Chicken Karahi available?" is search_menu.
- "Do you have Chicken Karahi?" is search_menu.

For quantity changes:
- distinguish operation set, increment, decrement, or remove.
- An explicit removal quantity is decrement.
- remove is for deleting the entire item from the cart.

Examples:

Customer: "Order 2 Chicken Karahi"
Output:
{{"intent":"add_item","item_name":"Chicken Karahi","query":null,"meal_type":null,"quantity":2,"operation":"add","day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}

Customer: "I want 2 chicken karahi please"
Output:
{{"intent":"add_item","item_name":"Chicken Karahi","query":null,"meal_type":null,"quantity":2,"operation":"add","day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}

Customer: "Can I get one Chicken Karahi?"
Output:
{{"intent":"add_item","item_name":"Chicken Karahi","query":null,"meal_type":null,"quantity":1,"operation":"add","day":null,"order_number":null,"address":null,"confidence":0.96,"multiple_intents":false}}

Customer: "How much is Chicken Karahi?"
Output:
{{"intent":"search_menu","item_name":null,"query":"Chicken Karahi","meal_type":null,"quantity":null,"operation":null,"day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}

Customer: "Is Chicken Karahi available?"
Output:
{{"intent":"search_menu","item_name":null,"query":"Chicken Karahi","meal_type":null,"quantity":null,"operation":null,"day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}

Customer: "Give me 2 Chicken Karahi"
Output:
{{"intent":"add_item","item_name":"Chicken Karahi","query":null,"meal_type":null,"quantity":2,"operation":"add","day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}

Customer: "I need Chicken Karahi"
Output:
{{"intent":"add_item","item_name":"Chicken Karahi","query":null,"meal_type":null,"quantity":null,"operation":"add","day":null,"order_number":null,"address":null,"confidence":0.96,"multiple_intents":false}}

Customer: "Do you have Chicken Karahi?"
Output:
{{"intent":"search_menu","item_name":null,"query":"Chicken Karahi","meal_type":null,"quantity":null,"operation":null,"day":null,"order_number":null,"address":null,"confidence":0.98,"multiple_intents":false}}
JSON shape:
{{"intent":"unknown","item_name":null,"query":null,"meal_type":null,"quantity":null,"operation":null,"day":null,"order_number":null,"address":null,"confidence":0.0,"multiple_intents":false}}

Customer message: {message}
"""

    async def classify(self, message: str) -> IntentClassification | None:
        if not normalize_text(message):
            return None

        started = time.perf_counter()
        logger.info("classifier_invocation_begin", extra={
            "event": "classifier_invocation_begin",
        })
        try:
            if not settings.OPENAI_API_KEY.strip() and isinstance(self.llm, OpenAIService):
                logger.warning("classifier_invocation_failed", extra={
                    "event": "classifier_invocation_failed",
                    "reason": "configuration_missing",
                    "exception_type": "ConfigurationError",
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                })
                return None

            raw = await self.llm.generate_response(self.build_prompt(message))
            if not raw.strip():
                logger.warning("classifier_invocation_failed", extra={
                    "event": "classifier_invocation_failed",
                    "reason": "empty_model_response",
                    "exception_type": None,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                })
                return None

            parsed: Any = json.loads(raw)
            result = IntentClassification.model_validate(parsed)
            if result.intent == "weekday_menu":
                result = result.model_copy(update={"intent": "today_menu"})
            if result.intent == "policy_question":
                result = result.model_copy(update={"intent": "faq"})
            logger.info("classifier_invocation_success", extra={
                "event": "classifier_invocation_success",
                "intent": result.intent,
                "confidence": result.confidence,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return result
        except json.JSONDecodeError:
            logger.warning("classifier_invocation_failed", extra={
                "event": "classifier_invocation_failed",
                "reason": "malformed_json",
                "exception_type": "JSONDecodeError",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return None
        except ValidationError:
            logger.warning("classifier_invocation_failed", extra={
                "event": "classifier_invocation_failed",
                "reason": "schema_validation_failed",
                "exception_type": "ValidationError",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return None
        except Exception as exc:
            logger.warning("classifier_invocation_failed", extra={
                "event": "classifier_invocation_failed",
                "reason": "model_error",
                "exception_type": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return None
