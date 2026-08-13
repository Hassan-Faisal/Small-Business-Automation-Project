from __future__ import annotations

import asyncio
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


class SemanticContext(BaseModel):
    """Bounded, non-authoritative context supplied to semantic interpretation."""

    model_config = ConfigDict(extra="ignore")

    message: str = Field(max_length=1000)
    recent_turns: list[dict[str, str]] = Field(default_factory=list, max_length=8)
    cart_items: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    pending_clarification: dict[str, object] | None = None
    pending_options: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    catalog_items: list[dict[str, object]] = Field(default_factory=list, max_length=50)
    active_order: dict[str, object] = Field(default_factory=dict)


class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: ClassifierIntent
    item_name: str | None = Field(default=None, max_length=120)
    referenced_item: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=120)
    meal_type: str | None = Field(default=None, max_length=20)
    quantity: int | None = Field(default=None, ge=1, le=50)
    operation: CartOperation | None = None
    day: str | None = Field(default=None, max_length=20)
    order_number: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    multiple_intents: bool = False
    needs_clarification: bool = False
    include_terms: list[str] = Field(default_factory=list, max_length=20)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)

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
    """Structured semantic interpretation with bounded conversational context."""

    confidence_threshold = 0.78

    def __init__(self, llm: OpenAIService | None = None) -> None:
        self.llm = llm or OpenAIService()

    @staticmethod
    def build_prompt(context: SemanticContext | str) -> str:
        semantic_context = context if isinstance(context, SemanticContext) else SemanticContext(message=context)
        payload = json.dumps(semantic_context.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
        return f"""Interpret the customer message for a food-ordering conversation. Return JSON only.

You are a semantic interpreter, not the business system. Understand flexible English and Roman Urdu wording from the current message and bounded context. Resolve references to a catalog label only when the context makes the reference unambiguous.

Supported intents: greeting, today_menu, weekly_menu, weekday_menu, add_item, view_cart, search_menu, cart_total, remove_item, set_quantity, increment_quantity, decrement_quantity, change_quantity, clear_cart, confirm_order, provide_address, track_order, cancel_order, modify_order, subscription_plans, create_subscription, subscription_status, pause_subscription, resume_subscription, cancel_subscription, skip_meal, bulk_order, policy_question, faq, delivery_area, delivery_timing, payment_methods, human_handoff, unknown.

Return an object with these fields:
intent, item_name, referenced_item, query, meal_type, quantity, operation, day, order_number, address, confidence, multiple_intents, needs_clarification, include_terms, exclude_terms.
Use null for unavailable scalar fields and [] for list fields.

Rules:
- For food actions, item_name must contain the customer's requested food entity, normalized to the closest catalog label only when supported by catalog context. It is not a final database identity.
- Use referenced_item for contextual references when useful; do not invent a product.
- Interpret quantity changes and removals as operations, not as permission to calculate totals.
- Set needs_clarification=true when context is missing or more than one candidate can satisfy the reference.
- Never decide price, total, availability, authorization, order status, cancellation eligibility, or final database identity.
- A product is valid only after deterministic database/catalog resolution by the application.

Bounded context:
{payload}
"""

    async def classify(self, context: SemanticContext | str, *, message_id: str | None = None) -> IntentClassification | None:
        semantic_context = context if isinstance(context, SemanticContext) else SemanticContext(message=context)
        if not normalize_text(semantic_context.message):
            return None

        started = time.perf_counter()
        # Some integrations can globally disable already-created loggers via
        # logging configuration. Semantic diagnostics must remain observable.
        logger.disabled = False
        context_counts = {
            "recent_turn_count": len(semantic_context.recent_turns),
            "cart_item_count": len(semantic_context.cart_items),
            "pending_option_count": len(semantic_context.pending_options),
            "catalog_item_count": len(semantic_context.catalog_items),
            "active_order_present": bool(semantic_context.active_order),
        }
        logger.info("classifier_started", extra={"event": "classifier_started", "message_id": message_id or "unknown", "model": settings.OPENAI_MODEL, **context_counts})
        logger.info("classifier_invocation_begin", extra={"event": "classifier_invocation_begin"})
        try:
            if not settings.OPENAI_API_KEY.strip() and isinstance(self.llm, OpenAIService):
                logger.warning("classifier_failed", extra={"event": "classifier_failed", "message_id": message_id or "unknown", "category": "configuration", "exception_type": "ConfigurationError", "safe_exception_summary": "OPENAI_API_KEY is not configured", "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
                return None
            raw = await self.llm.generate_response(self.build_prompt(semantic_context))
            if not raw.strip():
                logger.warning("classifier_failed", extra={"event": "classifier_failed", "message_id": message_id or "unknown", "category": "empty_response", "exception_type": "EmptyResponse", "safe_exception_summary": "model returned an empty response", "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
                return None
            result = IntentClassification.model_validate(json.loads(raw))
            if result.intent == "weekday_menu":
                result = result.model_copy(update={"intent": "today_menu"})
            if result.intent == "policy_question":
                result = result.model_copy(update={"intent": "faq"})
            logger.info("classifier_completed", extra={"event": "classifier_completed", "message_id": message_id or "unknown", "intent": result.intent, "item_name": result.item_name or "", "referenced_item": result.referenced_item or "", "quantity": result.quantity if result.quantity is not None else "", "operation": result.operation or "", "confidence": result.confidence, "needs_clarification": result.needs_clarification, "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
            return result
        except json.JSONDecodeError:
            logger.warning("classifier_failed", extra={"event": "classifier_failed", "message_id": message_id or "unknown", "category": "malformed_json", "exception_type": "JSONDecodeError", "safe_exception_summary": "model response was not valid JSON", "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        except ValidationError:
            logger.warning("classifier_failed", extra={"event": "classifier_failed", "message_id": message_id or "unknown", "category": "validation", "exception_type": "ValidationError", "safe_exception_summary": "structured response failed schema validation", "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        except Exception as exc:
            exception_type = type(exc).__name__
            lowered_type = exception_type.lower()
            category = "timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in lowered_type else "api" if any(token in lowered_type for token in ("api", "openai", "http", "connection", "rate", "authentication")) else "unexpected"
            summary = str(exc)
            configured_key = settings.OPENAI_API_KEY.strip()
            if configured_key:
                summary = summary.replace(configured_key, "[redacted]")
            summary = " ".join(summary.split())[:200] or "no exception detail"
            logger.warning("classifier_failed", extra={"event": "classifier_failed", "message_id": message_id or "unknown", "category": category, "exception_type": exception_type, "safe_exception_summary": summary, "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        return None
