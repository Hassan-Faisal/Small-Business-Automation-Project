from __future__ import annotations

from datetime import date, timedelta
import re
import time
from decimal import Decimal
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import setup_logger
from app.langgraph.memory import ConversationMemory
from app.langgraph.classifier import SemanticContext, StructuredIntentClassifier
from app.langgraph.parsing import (
    CANONICAL_INTENTS,
    extract_day,
    extract_discovery_query,
    extract_search_constraints,
    extract_meal_type,
    extract_order_reference,
    extract_position_reference,
    extract_quantity,
    infer_intent,
    normalize_text,
)
from app.langgraph.state import ConversationState
from app.langgraph.tools import calculate_cart_total, create_order_payload
from app.models.customer_subscription import CustomerSubscription
from app.models.order import Order
from app.models.product import Product
from app.rag.rag_chain import RAGChain
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.tiffin_service import BULK_ORDER_THRESHOLD, SubscriptionService, TiffinCatalogService, TiffinPolicyService, WEEKDAYS

logger = setup_logger(__name__)
MEAL_TYPES = ("breakfast", "lunch", "dinner")
DEFAULT_REPLY = "Sorry, I didn't quite understand that.\n\nYou can ask me to:\n- Show today's or weekly menu\n- Add a meal to your cart\n- Show your cart\n- Place or track an order\n\nTry something like 'show my cart' or 'today's menu'."
POLICY_FALLBACK = "I could not find that information in the TiffinAI policy documents. Please contact support."
MAX_MENU_REPLY_LENGTH = 1500
WELCOME_MESSAGE = "Assalam o Alaikum! " + chr(0x1F44B) + " Welcome to TiffinAI.\n\nHungry? I'm here to make ordering easy.\n\nYou can type naturally, for example:\n- What's on today's menu?\n- Show me Friday's menu\n- I want to order Chicken Biryani\n- Show my cart\n- Track my order\n\nWhat would you like to eat today?"


class OrderConversationWorkflow:
    def __init__(self, rag_chain: RAGChain, product_service: ProductService, order_service: OrderService, memory: ConversationMemory | None = None, meal_service: TiffinCatalogService | None = None, classifier: StructuredIntentClassifier | None = None) -> None:
        self.rag_chain = rag_chain
        self.product_service = product_service
        self.order_service = order_service
        if memory is not None:
            self.memory = memory
        else:
            session = getattr(product_service, "db", None)
            if not isinstance(session, Session):
                raise ValueError("ConversationMemory requires a SQLAlchemy session.")
            self.memory = ConversationMemory(session)
        self.meal_service = meal_service
        self.classifier = classifier or StructuredIntentClassifier()
        self.graph = self._build_graph()

    def _load_context(self, conversation_id: str) -> dict[str, object]:
        return self.memory.get(conversation_id)

    def _normalize_response_text(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("reply_text", "response", "message", "content", "text"):
                nested = value.get(key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        return str(value).strip()

    def _reply(self, value: object) -> str:
        text = self._normalize_response_text(value)
        return text or DEFAULT_REPLY

    @staticmethod
    def _price(value: object) -> str:
        return f"Rs. {Decimal(str(value)):.2f}"

    @staticmethod
    def _phone(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _message_day(reference: str, *, base_date: date | None = None) -> str:
        current_date = base_date or date.today()
        return extract_day(reference, base_date=current_date) or current_date.strftime("%A")

    @staticmethod
    def _looks_like_address(message: str) -> bool:
        normalized = normalize_text(message)
        if len(normalized) < 10:
            return False
        address_keywords = {"street", "st", "road", "rd", "house", "sector", "block", "phase", "apartment", "flat", "floor", "town", "near"}
        has_digits = any(character.isdigit() for character in normalized)
        has_keyword = any(keyword in normalized for keyword in address_keywords)
        return (has_digits and has_keyword) or ("," in message and has_digits)

    def _append_messages(self, state: ConversationState, memory_state: dict[str, object], reply: str) -> list[dict[str, Any]]:
        messages = list(memory_state.get("messages", []))
        user_message = {"role": "user", "content": str(state.get("last_user_message", ""))}
        assistant_message: dict[str, Any] = {"role": "assistant", "content": reply}
        options = state.get("displayed_options")
        if isinstance(options, list) and options:
            assistant_message["options"] = options
            assistant_message["context_type"] = str(state.get("displayed_context_type") or "")
            pending_action = str(state.get('pending_action') or '')
            if not pending_action:
                pending_action = 'add_item' if str(state.get('displayed_context_type') or '') in {'add_item', 'menu'} else 'search_menu' if str(state.get('displayed_context_type') or '') == 'menu_search' else ''
            if pending_action:
                assistant_message['pending_action'] = pending_action
        clarification = state.get("pending_clarification")
        if isinstance(clarification, dict):
            assistant_message["clarification"] = clarification
        if not messages or messages[-1] != user_message:
            messages.append(user_message)
        messages.append(assistant_message)
        return messages

    def _message_options(self, messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        for message in reversed(messages):
            if message.get("role") == "assistant":
                if isinstance(message.get("options"), list):
                    return str(message.get("context_type") or "") or None, list(message.get("options") or [])
                return None, []
        return None, []

    def _message_pending_action(self, messages: list[dict[str, Any]]) -> str | None:
        for message in reversed(messages):
            if message.get('role') == 'assistant':
                action = message.get('pending_action')
                return str(action) if action else None
        return None

    def _message_clarification(self, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        for message in reversed(messages):
            if message.get("role") == "assistant":
                clarification = message.get("clarification")
                return dict(clarification) if isinstance(clarification, dict) else None
        return None

    def _resolve_context_option(self, memory_state: dict[str, object], message: str) -> dict[str, Any] | None:
        context_type, options = self._message_options(list(memory_state.get("messages", [])))
        if not context_type or not options:
            return None
        normalized_message = normalize_text(message)
        position = extract_position_reference(message)
        if position is None and normalized_message.isdigit():
            position = int(normalized_message)
        if position is not None:
            index = position - 1 if position > 0 else len(options) - 1
            return options[index] if 0 <= index < len(options) else None
        if context_type in {"add_item", "menu_search"}:
            for option in options:
                label = normalize_text(str(option.get("label") or option.get("name") or ""))
                if label and normalized_message == label:
                    return option

        if context_type == "menu_day":
            selected_day = extract_day(message)
            if selected_day is not None:
                for option in options:
                    if str(option.get("day") or "").lower() == selected_day.lower():
                        return option
        return None

    def _should_defer_active_cart_semantics(
        self,
        intent: str,
        message: str,
        memory_state: dict[str, object],
        customer_phone: str | None,
    ) -> bool:
        """Let structured semantics arbitrate broad order language over known state."""
        if intent != "add_item" or extract_order_reference(message) is not None:
            return False
        has_active_cart = bool(list(memory_state.get("cart", [])))
        has_recent_order = False
        phone = self._phone(customer_phone or memory_state.get("customer_phone"))
        if not has_active_cart and phone:
            has_recent_order = self.order_service.retrieve_latest_order_for_customer(phone) is not None
        if not has_active_cart and not has_recent_order:
            return False
        # A resolvable product is strong evidence for a real add request. If the
        # broad parser only saw "order" but no product exists in the message,
        # defer to cart-summary, checkout, or modify-order semantics.
        return not bool(self._resolve_products(message))

    def _should_defer_menu_search(self, intent: str, message: str) -> bool:
        if intent not in {"today_menu", "breakfast_menu", "lunch_menu", "dinner_menu"} or self.meal_service is None:
            return False
        normalized = normalize_text(message)
        excluded = {"breakfast", "lunch", "dinner", "menu", "today", "tomorrow"}
        for offering in self.meal_service.list_meal_offerings(active_only=True):
            for token in offering.name.lower().split():
                token = "".join(character for character in token if character.isalnum())
                if len(token) >= 4 and token not in excluded and token in normalized:
                    return True
        return False

    def _semantic_context(self, message: str, memory_state: dict[str, object]) -> SemanticContext:
        raw_messages = list(memory_state.get("messages", []))
        recent_turns: list[dict[str, str]] = []
        for entry in raw_messages[-8:]:
            if not isinstance(entry, dict):
                continue
            role = str(entry.get("role") or "")
            content = str(entry.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                recent_turns.append({"role": role, "content": content[:240]})

        pending_context, pending_options = self._message_options(raw_messages)
        bounded_options = [
            {key: value for key, value in option.items() if key in {"label", "name", "day", "meal_type"}}
            for option in pending_options[:20]
            if isinstance(option, dict)
        ]
        catalog_items: list[dict[str, object]] = []
        seen_names: set[str] = set()
        try:
            products = self.product_service.list_available_products()
        except Exception:
            products = []
        for product in products[:50]:
            name = str(product.name).strip()
            if name and name.lower() not in seen_names:
                seen_names.add(name.lower())
                catalog_items.append({"name": name})
        if self.meal_service is not None and len(catalog_items) < 50:
            try:
                offerings = self.meal_service.list_meal_offerings(active_only=True)
            except Exception:
                offerings = []
            for offering in offerings:
                name = str(offering.name).strip()
                if name and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    catalog_items.append({"name": name, "day": offering.day_of_week, "meal_type": offering.meal_type})
                if len(catalog_items) >= 50:
                    break

        cart_items = [
            {"name": str(item.get("name") or ""), "quantity": int(item.get("quantity") or 0)}
            for item in list(memory_state.get("cart", []))[:20]
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        active_order = {
            key: memory_state.get(key)
            for key in ("order_number", "order_status")
            if memory_state.get(key) is not None
        }
        clarification = self._message_clarification(raw_messages)
        return SemanticContext(
            message=message[:1000],
            recent_turns=recent_turns,
            cart_items=cart_items,
            pending_clarification=clarification,
            pending_options=bounded_options,
            catalog_items=catalog_items,
            active_order=active_order,
        )

    async def _route_intent(self, state: ConversationState) -> ConversationState:
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        message = str(state.get("last_user_message", ""))
        deterministic_intent = infer_intent(message)
        logger.info("semantic_route_started", extra={"event": "semantic_route_started", "message_id": state.get("message_id") or "unknown", "conversation_id": state.get("conversation_id") or "unknown", "deterministic_intent": deterministic_intent})
        intent = deterministic_intent
        semantic_intents = {"add_item", "remove_item", "change_quantity", "search_menu", "clear_cart"}
        if deterministic_intent in semantic_intents:
            intent = "fallback"
        if self._should_defer_menu_search(intent, message):
            intent = "fallback"
        if self._should_defer_active_cart_semantics(intent, message, memory_state, str(state.get("customer_phone") or "")):
            intent = "fallback"
        intent_source = "deterministic" if intent != "fallback" else "fallback"
        intent_confidence = 1.0 if intent != "fallback" else 0.0
        pending_context, pending_options = self._message_options(list(memory_state.get("messages", [])))
        pending_clarification = self._message_clarification(list(memory_state.get("messages", [])))
        pending_action = self._message_pending_action(list(memory_state.get("messages", [])))
        selection_rejected = False
        selected = self._resolve_context_option(memory_state, message)
        if pending_options and selected is None and (pending_context == "menu_search" or (pending_context == "add_item" and pending_clarification is not None)):
            normalized_message = normalize_text(message)
            is_demonstrative_reference = any(token in normalized_message.split() for token in {"that", "this", "it", "one"})
            if extract_position_reference(message) is not None or normalized_message.isdigit():
                state["pending_clarification"] = pending_clarification
                state["displayed_options"] = pending_options
                state["displayed_context_type"] = "add_item"
                lines = ["I found these matching meals:"]
                lines.extend(f"{index}. {option.get('name') or option.get('label')} ({self._price(option.get('price') or 0)})" for index, option in enumerate(pending_options, start=1))
                lines.append("Reply with a number or exact meal name to add it.")
                state["clarification_response"] = "\\n".join(lines)
                if pending_context == "menu_search":
                    state["clarification_response"] = "Which meal would you like to add? Reply with a number or exact meal name."
                state["pending_action"] = "add_item" if pending_context == "add_item" or intent == "add_item" else "search_menu"
                selection_rejected = True
                intent = "fallback"
                selection_rejected = True
        if selected is not None:
            context_type, _ = self._message_options(list(memory_state.get("messages", [])))
            clarification = self._message_clarification(list(memory_state.get("messages", [])))
            if context_type == "plans":
                intent = "create_subscription"
                state["pending_subscription_plan"] = selected
            elif context_type == "menu":
                intent = "add_item"
                state["pending_menu_option"] = selected
            elif context_type == "add_item":
                intent = "add_item"
                state["pending_menu_option"] = selected
                if clarification is not None:
                    state["pending_clarification"] = clarification
            elif context_type == "menu_search":
                if deterministic_intent in {"add_item", "remove_item", "change_quantity"}:
                    state["pending_menu_option"] = selected
                    state["pending_clarification"] = {"type": "product_selection", "operation": "add", "quantity": int(state.get("classified_quantity") or 1)}
                    state["pending_action"] = "add_item"
                    intent = "add_item"
                else:
                    intent = "search_menu"
                    state["selected_menu_option"] = selected
                    state["classified_query"] = str(selected.get("name") or selected.get("label") or "")
            elif context_type == "menu_day":
                intent = "today_menu"
                state["selected_menu_day"] = str(selected.get("day") or "")
        if intent == "fallback" and deterministic_intent in {"fallback", "provide_address"} and self._looks_like_address(message):
            has_checkout_context = bool(memory_state.get("cart")) or bool(memory_state.get("address"))
            has_subscription_context = bool(self._phone(state.get("customer_phone") or memory_state.get("customer_phone")))
            if has_checkout_context or has_subscription_context:
                intent = "provide_address"
        if intent == "fallback" and not selection_rejected:
            started = time.perf_counter()
            classification = None
            semantic_context = self._semantic_context(message, memory_state)
            logger.info("semantic_context_built", extra={"event": "semantic_context_built", "message_id": state.get("message_id") or "unknown", "recent_turn_count": len(semantic_context.recent_turns), "cart_item_count": len(semantic_context.cart_items), "pending_option_count": len(semantic_context.pending_options), "catalog_item_count": len(semantic_context.catalog_items), "active_order_present": bool(semantic_context.active_order)})
            try:
                classification = await self.classifier.classify(semantic_context, message_id=str(state.get("message_id") or "") or None)
            except (TypeError, AttributeError):
                try:
                    classification = await self.classifier.classify(semantic_context)
                except (TypeError, AttributeError):
                    classification = await self.classifier.classify(message)
            if classification is not None and classification.confidence >= self.classifier.confidence_threshold:
                intent_source = "llm_fallback"
                intent_confidence = classification.confidence
                intent = str(classification.intent)
                state["cart_operation"] = classification.operation
                if intent == "cart_total":
                    intent = "view_cart"
                    state["cart_view_mode"] = "total"
                elif intent == "set_quantity":
                    intent = "change_quantity"
                    state["cart_operation"] = "set"
                elif intent == "increment_quantity":
                    intent = "change_quantity"
                    state["cart_operation"] = "increment"
                elif intent == "decrement_quantity":
                    intent = "change_quantity"
                    state["cart_operation"] = "decrement"
                elif intent == "remove_item":
                    state["cart_operation"] = classification.operation or ("decrement" if classification.quantity is not None else "remove")
                state["classified_item_name"] = classification.item_name
                state["classified_referenced_item"] = classification.referenced_item
                state["needs_clarification"] = classification.needs_clarification
                state["classified_query"] = classification.query
                state["classified_meal_type"] = classification.meal_type
                state["classified_quantity"] = classification.quantity
                state["classified_day"] = classification.day
                state["classified_order_number"] = classification.order_number
                state["classified_address"] = classification.address
                state["classified_include_terms"] = list(getattr(classification, "include_terms", []) or [])
                state["classified_exclude_terms"] = list(getattr(classification, "exclude_terms", []) or [])
                if deterministic_intent == "add_item" and intent == "search_menu":
                    direct_matches = self._resolve_products(message)
                    if direct_matches:
                        intent = "add_item"
                    elif pending_context == "menu_search":
                        intent = "fallback"
                        state["clarification_response"] = "Which meal would you like to add? Reply with a number or exact meal name."
                if classification.multiple_intents or classification.needs_clarification:
                    intent = "fallback"
                    state["clarification_response"] = "I need a little more detail to identify the right meal or action. Which item did you mean?" if classification.needs_clarification else "I can help with one action at a time. Would you like to see the menu, or add an item first?"
            if classification is None and deterministic_intent == "add_item" and self._resolve_products(message):
                intent = "add_item"
                intent_source = "deterministic_fallback"
                intent_confidence = 1.0
            elif classification is None and pending_options:
                state["displayed_options"] = pending_options
                state["displayed_context_type"] = pending_context or "add_item"
                state["clarification_response"] = "Please choose one of these options:\\n" + "\\n".join(f"{index}. {option.get('name') or option.get('label')}" for index, option in enumerate(pending_options, start=1))
                selection_rejected = True
                intent = "fallback"
            elif classification is not None:
                logger.info("classifier_result_rejected", extra={"event": "classifier_result_rejected", "reason": "confidence_below_threshold", "intent": classification.intent, "confidence": classification.confidence, "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
        if intent == "fallback" and deterministic_intent != "fallback" and not selection_rejected and intent_source == "fallback":
            intent = deterministic_intent
            intent_source = "deterministic_fallback"
            intent_confidence = 1.0
        state["intent_source"] = intent_source
        state["intent_confidence"] = intent_confidence
        logger.info("intent_classified", extra={"event": "intent_classified", "intent_source": intent_source, "predicted_intent": intent if intent in CANONICAL_INTENTS else "fallback", "confidence": intent_confidence, "clarification_required": intent == "fallback"})
        state["intent"] = intent if intent in CANONICAL_INTENTS else "fallback"
        workflow_node = {"today_menu": "menu", "weekly_menu": "menu", "breakfast_menu": "menu", "lunch_menu": "menu", "dinner_menu": "menu", "subscription_plans": "subscription", "create_subscription": "subscription", "subscription_status": "subscription", "pause_subscription": "subscription", "resume_subscription": "subscription", "cancel_subscription": "subscription", "skip_meal": "subscription", "bulk_order": "subscription", "delivery_area": "rag", "delivery_timing": "rag", "faq": "rag", "payment_methods": "payment_methods"}.get(state["intent"], state["intent"])
        logger.info("workflow_node_selected", extra={"event": "workflow_node_selected", "message_id": state.get("message_id") or "unknown", "intent": state["intent"], "node": workflow_node})
        return state

    def _greeting(self, state: ConversationState) -> ConversationState:
        state["last_response"] = WELCOME_MESSAGE
        return state

    @staticmethod
    def _limit_daily_menu(text: str) -> str:
        continuation = "\n\nThis menu is long. Ask for breakfast, lunch, or dinner separately."
        if len(text) <= MAX_MENU_REPLY_LENGTH:
            return text
        available = MAX_MENU_REPLY_LENGTH - len(continuation)
        shortened = text[:available].rsplit(" ", 1)[0].rstrip()
        return shortened + continuation

    def _format_daily_menu(self, day_of_week: str, meal_type: str | None = None) -> str:
        if self.meal_service is None:
            return "Today's menu is not available yet. Please try again shortly or type 'weekly menu' to view the full plan."
        day_name = day_of_week.strip().title()
        if meal_type is None:
            menu = self.meal_service.list_daily_menu(day_name)
            if all(not menu.get(name) for name in MEAL_TYPES):
                return "Today's menu is not available yet. Please try again shortly or type 'weekly menu' to view the full plan."
            lines = [f"{day_name} menu:"]
            for current_meal in MEAL_TYPES:
                items = menu.get(current_meal, [])
                if items:
                    lines.append(f"{current_meal.title()}:")
                    lines.extend(f"- {item.name} ({self._price(item.price)})" for item in items)
            return self._limit_daily_menu("\n".join(lines))
        items = self.meal_service.list_meals_for_day_and_type(day_name, meal_type)
        if not items:
            return f"No {meal_type} meals are available for {day_name} yet."
        lines = [f"{day_name} {meal_type} menu:"]
        lines.extend(f"- {item.name} ({self._price(item.price)})" for item in items)
        return self._limit_daily_menu("\n".join(lines))

    def _format_weekly_menu(self) -> tuple[str, list[dict[str, Any]]]:
        if self.meal_service is None:
            return "Weekly menu is not available yet. Please try again shortly.", []
        weekly_menu = self.meal_service.list_weekly_menu()
        if not any(any(day_menu.get(meal_type) for meal_type in MEAL_TYPES) for day_menu in weekly_menu.values()):
            return "Weekly menu is not available yet. Please try again shortly.", []
        lines = ["Choose a day to view its menu:"]
        options = [{"label": day, "day": day} for day in WEEKDAYS]
        lines.extend(f"{index}. {day}" for index, day in enumerate(WEEKDAYS, start=1))
        return "\n".join(lines), options
    def _resolve_products(
        self,
        message: str,
        pending_option: dict[str, Any] | None = None,
        item_name: str | None = None,
        candidates: list[Product] | None = None,
        *,
        message_id: str | None = None,
        query_source: str | None = None,
    ) -> list[Product]:
        if pending_option and pending_option.get("name"):
            query = str(pending_option["name"])
        else:
            query = item_name or message
        matches = self.product_service.resolve_available_products(query, candidates=candidates)
        source = query_source or ("item_name" if item_name else "raw_message")
        query_preview = "[redacted]" if source == "raw_message" else " ".join(query.split())[:120]
        selected = matches[0] if len(matches) == 1 else None
        logger.info(
            "product_resolution",
            extra={
                "event": "product_resolution",
                "message_id": message_id or "unknown",
                "query_source": source,
                "query_preview": query_preview,
                "candidate_count": len(matches),
                "selected_product_id": getattr(selected, "id", "") if selected else "",
                "selected_product_name": getattr(selected, "name", "") if selected else "",
            },
        )
        return matches

    @staticmethod
    def _merge_search_constraints(
        message: str,
        state: ConversationState | None = None,
    ) -> dict[str, list[str]]:
        parsed = extract_search_constraints(message)
        state = state or {}
        include_terms = list(parsed["include_terms"])
        exclude_terms = list(parsed["exclude_terms"])
        for key, target in (("classified_include_terms", include_terms), ("classified_exclude_terms", exclude_terms)):
            values = state.get(key, [])
            if isinstance(values, list):
                target.extend(str(value).strip().lower() for value in values if str(value).strip())
        exclude_terms = list(dict.fromkeys(exclude_terms))
        include_terms = [term for term in dict.fromkeys(include_terms) if term not in exclude_terms]
        return {"include_terms": include_terms, "exclude_terms": exclude_terms}
    def _discover_meal_offerings(
        self,
        message: str,
        query: str | None = None,
        state: ConversationState | None = None,
    ) -> tuple[str, dict[str, list[str]], list[Any]]:
        if self.meal_service is None:
            return "", {"include_terms": [], "exclude_terms": []}, []
        constraints = self._merge_search_constraints(message, state)
        search_query = (query or extract_discovery_query(message)).strip()
        day = extract_day(message)
        meal_type = extract_meal_type(message)
        matches = self.meal_service.search_meal_offerings(
            search_query,
            day_of_week=day,
            meal_type=meal_type,
            include_terms=constraints["include_terms"],
            exclude_terms=constraints["exclude_terms"],
        )
        return search_query, constraints, matches
    def _add_item(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        cart = list(memory_state.get("cart", []))
        pending_option = state.get("pending_menu_option") if isinstance(state.get("pending_menu_option"), dict) else None
        pending_clarification = state.get("pending_clarification") if isinstance(state.get("pending_clarification"), dict) else None
        classified_item_name = state.get("classified_item_name")
        classified_referenced_item = state.get("classified_referenced_item")
        matches = self._resolve_products(
            str(state.get("last_user_message", "")),
            pending_option,
            classified_item_name or classified_referenced_item,
            message_id=str(state.get("message_id") or "") or None,
            query_source="item_name" if classified_item_name else "referenced_item" if classified_referenced_item else "raw_message",
        )
        if not matches:
            discovery_query, constraints, discovered = self._discover_meal_offerings(
                str(state.get("last_user_message", "")),
                state.get("classified_item_name"),
                state,
            )
            if discovered:
                options = [{"label": offering.name, "name": offering.name, "price": str(offering.price)} for offering in discovered]
                state["displayed_options"] = options
                state["displayed_context_type"] = "add_item"
                state["pending_action"] = "add_item"
                requested_quantity = state.get("classified_quantity") or extract_quantity(str(state.get("last_user_message", ""))) or 1
                state["pending_clarification"] = {"type": "product_selection", "operation": "add", "quantity": int(requested_quantity)}
                lines = ["I found these catalog options:"]
                lines.extend(f"{index}. {option['name']} ({self._price(option['price'])})" for index, option in enumerate(options, start=1))
                lines.append("Reply with a number or exact meal name to add it.")
                state["cart"] = cart
                state["last_response"] = "\n".join(lines)
                return state
            state["cart"] = cart
            if constraints["exclude_terms"] or constraints["include_terms"] or extract_meal_type(str(state.get("last_user_message", ""))):
                state["last_response"] = "I could not verify a matching meal from the catalog. The menu does not include enough structured ingredient information to make that preference safely."
            else:
                state["last_response"] = "I could not find that meal in the menu. Type 'today menu' or 'weekly menu' to see available meals."
            return state
        if len(matches) > 1:
            options = [{"label": product.name, "name": product.name, "price": str(product.price)} for product in matches]
            state["displayed_options"] = options
            state["displayed_context_type"] = "add_item"
            state["pending_action"] = "add_item"
            requested_quantity = state.get("classified_quantity")
            if requested_quantity is None:
                requested_quantity = extract_quantity(str(state.get("last_user_message", "")))
            state["pending_clarification"] = {
                "type": "product_selection",
                "operation": "add",
                "quantity": int(requested_quantity) if requested_quantity is not None else 1,
            }
            lines = ["I found these matching meals:"]
            lines.extend(f"{option}. {product.name} ({self._price(product.price)})" for option, product in enumerate(matches, start=1))
            lines.append("Reply with a number or exact meal name to add it.")
            state["last_response"] = "\n".join(lines)
            return state
        product = matches[0]
        if pending_option is not None and pending_clarification is not None:
            quantity = int(pending_clarification.get("quantity") or 1)
        else:
            message_quantity = extract_quantity(str(state.get("last_user_message", "")))
            quantity = message_quantity if message_quantity is not None else (state.get("classified_quantity") or 1)
        if quantity <= 0:
            state["cart"] = cart
            state["last_response"] = "Quantity must be greater than zero."
            return state
        existing = next((item for item in cart if int(item.get("product_id", 0)) == product.id), None)
        if existing is not None:
            quantity += int(existing.get("quantity", 0))
        subtotal = product.price * quantity
        updated_cart = [item for item in cart if int(item.get("product_id", 0)) != product.id]
        updated_cart.append({"product_id": product.id, "name": product.name, "quantity": quantity, "unit_price": str(product.price), "subtotal": str(subtotal)})
        self.memory.save(conversation_id, cart=updated_cart, customer_phone=state.get("customer_phone"))
        state["cart"] = updated_cart
        state["pending_menu_option"] = None
        state["pending_clarification"] = None
        state["displayed_options"] = []
        state["displayed_context_type"] = ""
        state["pending_action"] = None
        state["last_response"] = f"Done! {product.name} has been added to your cart.\nCart subtotal: {self._price(calculate_cart_total(updated_cart))}\n\nWant to add anything else?"
        return state

    async def _search_menu(self, state: ConversationState) -> ConversationState:
        message = str(state.get("last_user_message", ""))
        query = str(state.get("classified_query") or state.get("classified_item_name") or state.get("classified_referenced_item") or extract_discovery_query(message)).strip()
        if query.lower() in {"item", "items", "meal", "meals", "option", "options"}:
            query = ""
        constraints = self._merge_search_constraints(message, state)
        if self.meal_service is None:
            state["last_response"] = "Please tell me what food or meal you want me to find."
            return state
        selected_option = state.get("selected_menu_option")
        if isinstance(selected_option, dict):
            selected_name = str(selected_option.get("name") or selected_option.get("label") or "meal")
            selected_price = self._price(selected_option.get("price") or 0)
            state["selected_menu_option"] = None
            state["displayed_options"] = []
            state["displayed_context_type"] = ""
            state["pending_action"] = None
            state["cart"] = list(self._load_context(str(state.get("conversation_id", "default"))).get("cart", []))
            state["last_response"] = f"{selected_name} is available for {selected_price}. Would you like to add it to your cart?"
            return state
        message = str(state.get("last_user_message", ""))
        day = state.get("classified_day") or extract_day(message)
        meal_type = state.get("classified_meal_type") or extract_meal_type(message)
        matches = self.meal_service.search_meal_offerings(query, day_of_week=str(day) if day else None, meal_type=str(meal_type) if meal_type else None, include_terms=constraints["include_terms"], exclude_terms=constraints["exclude_terms"])
        state["cart"] = list(self._load_context(str(state.get("conversation_id", "default"))).get("cart", []))
        if not matches:
            scope = ""
            if day:
                scope += f" on {day}"
            if meal_type:
                scope += f" during {meal_type}"
            constraint_description = " ".join(constraints["include_terms"] + constraints["exclude_terms"])
            description = query or constraint_description or (scope.strip() or "that request")
            state["last_response"] = f"I could not find any available meals matching {description}{scope if query else ""}."
            return state
        options = [{"label": item.name, "name": item.name, "price": str(item.price), "day": item.day_of_week, "meal_type": item.meal_type} for item in matches]
        state["displayed_options"] = options
        state["displayed_context_type"] = "menu_search"
        state["pending_action"] = "search_menu"
        heading = query or "Meals matching your request"
        lines = [f"{heading}:"]
        lines.extend(f"{index}. {item.name} ({self._price(item.price)})" for index, item in enumerate(matches, start=1))
        lines.append("Reply with a number or meal name to see that result again.")
        state["last_response"] = "\n".join(lines)
        return state


    def _clear_cart(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        self.memory.save(conversation_id, cart=[], customer_phone=state.get("customer_phone"))
        state["cart"] = []
        state["last_response"] = "Your cart has been cleared."
        return state

    def _change_quantity(self, state: ConversationState) -> ConversationState:
        message = normalize_text(str(state.get("last_user_message", "")))
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        cart = list(memory_state.get("cart", []))
        if not cart:
            state["last_response"] = "Your cart is empty."
            return state

        position = extract_position_reference(message)
        target_index: int | None = position - 1 if position and 0 < position <= len(cart) else None
        item_name = state.get("classified_item_name") or state.get("classified_referenced_item")
        if target_index is None:
            cart_products = [
                product for item in cart
                if (product := self.product_service.retrieve_product_by_id(int(item.get("product_id", 0)))) is not None
            ]
            query = str(item_name) if item_name else re.sub(r"\b(?:make|set|change|quantity|to|only|actually|just|instead|asked|for|i|meant|it|that|remove|delete|take|out|from|my|mery|order|cart|mein|mai|sai|se|hata|do|kar|kr)\b|\b\d+\b", " ", message).strip()
            matches = self._resolve_products(message, item_name=query, candidates=cart_products)
            if len(matches) > 1:
                state["cart"] = cart
                state["last_response"] = "I found more than one matching item in your cart. Which one should I update?"
                return state
            if matches:
                target_index = next(
                    index for index, item in enumerate(cart)
                    if int(item.get("product_id", 0)) == matches[0].id
                )
        if target_index is None:
            if len(cart) == 1:
                target_index = 0
            else:
                state["cart"] = cart
                state["last_response"] = "Which cart item should I update?"
                return state

        message_quantity = extract_quantity(message)
        requested = message_quantity if message_quantity is not None else state.get("classified_quantity")
        operation = str(state.get("cart_operation") or "")
        if not operation:
            operation = "increment" if ("add one more" in message or "again" in message) else "decrement" if ("decrease" in message or "reduce" in message) else "set"
        if requested is None or requested <= 0:
            state["cart"] = cart
            state["last_response"] = "Please tell me the quantity you want."
            return state

        target = cart[target_index]
        current_quantity = int(target.get("quantity", 0))
        if operation == "increment":
            new_quantity = current_quantity + requested
        elif operation == "decrement":
            new_quantity = current_quantity - requested
        else:
            new_quantity = requested

        if new_quantity <= 0:
            updated_cart = cart[:target_index] + cart[target_index + 1:]
            notice = f"Removed {target.get('name', 'meal')} from your cart."
        else:
            target["quantity"] = new_quantity
            target["subtotal"] = str(Decimal(str(target.get("unit_price", 0))) * new_quantity)
            updated_cart = cart
            notice = f"Updated {target.get('name', 'meal')} to {new_quantity}."

        self.memory.save(conversation_id, cart=updated_cart, customer_phone=state.get("customer_phone"))
        state["cart"] = updated_cart
        state["last_response"] = f"{notice} Cart total: {self._price(calculate_cart_total(updated_cart))}"
        return state

    def _cart_line(self, item: dict[str, object]) -> str:
        subtotal = Decimal(str(item.get("subtotal") or Decimal(str(item.get("unit_price", 0))) * int(item.get("quantity", 0))))
        return f"{int(item.get('quantity', 0))} \u00D7 {item.get('name', 'Meal')} \u2014 {self._price(subtotal)}"

    def _view_cart(self, state: ConversationState) -> ConversationState:
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        cart = list(memory_state.get("cart", []))
        if not cart:
            state["cart"] = []
            state["last_response"] = "Your cart is empty. Type 'today menu' or 'weekly menu' to see available meals."
            return state
        total = calculate_cart_total(cart)
        if state.get("cart_view_mode") == "total":
            state["cart"] = cart
            state["last_response"] = f"Your cart total is {self._price(total)}."
            return state
        lines = ["Your cart"]
        lines.extend(self._cart_line(item) for item in cart)
        lines.append("")
        lines.append(f"Total: {self._price(total)}")
        lines.append("Type 'confirm order' to continue.")
        state["cart"] = cart
        state["last_response"] = "\n".join(lines)
        return state

    def _remove_item(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        cart = list(memory_state.get("cart", []))
        if not cart:
            state["cart"] = []
            state["last_response"] = "Your cart is empty."
            return state

        message = normalize_text(str(state.get("last_user_message", "")))
        position = extract_position_reference(message)
        target_index: int | None = position - 1 if position and 0 < position <= len(cart) else None
        item_name = state.get("classified_item_name") or state.get("classified_referenced_item")
        if target_index is None:
            cart_products = [
                product for item in cart
                if (product := self.product_service.retrieve_product_by_id(int(item.get("product_id", 0)))) is not None
            ]
            query = str(item_name) if item_name else re.sub(r"\b(?:make|set|change|quantity|to|only|actually|just|instead|asked|for|i|meant|it|that|remove|delete|take|out|from|my|mery|order|cart|mein|mai|sai|se|hata|do|kar|kr)\b|\b\d+\b", " ", message).strip()
            matches = self._resolve_products(message, item_name=query, candidates=cart_products)
            if len(matches) > 1:
                state["cart"] = cart
                state["last_response"] = "I found more than one matching item in your cart. Which one should I remove?"
                return state
            if matches:
                target_index = next(
                    index for index, item in enumerate(cart)
                    if int(item.get("product_id", 0)) == matches[0].id
                )
        if target_index is None:
            generic_removal = message in {"remove", "delete", "take out", "remove item", "delete item"}
            semantic_removal = state.get("intent_source") == "llm_fallback" and str(state.get("cart_operation") or "remove") == "remove"
            if len(cart) == 1 and not item_name and position is None and (generic_removal or semantic_removal):
                target_index = 0
            else:
                state["cart"] = cart
                state["last_response"] = "Which cart item should I remove?"
                return state

        target = cart[target_index]
        requested_from_message = extract_quantity(message)
        operation = str(state.get("cart_operation") or "remove")
        if requested_from_message is not None and operation in {"", "remove"}:
            operation = "decrement"
        requested = requested_from_message if requested_from_message is not None else (state.get("classified_quantity") or 1)
        current_quantity = int(target.get("quantity", 0))
        if operation == "decrement":
            new_quantity = current_quantity - requested
        else:
            new_quantity = 0

        if new_quantity > 0:
            target["quantity"] = new_quantity
            target["subtotal"] = str(Decimal(str(target.get("unit_price", 0))) * new_quantity)
            updated_cart = cart
            notice = f"Removed {requested} x {target.get('name', 'meal')} from your cart."
        else:
            updated_cart = cart[:target_index] + cart[target_index + 1:]
            notice = f"Removed {target.get('name', 'meal')} from your cart."

        self.memory.save(conversation_id, cart=updated_cart, customer_phone=state.get("customer_phone"))
        state["cart"] = updated_cart
        state["last_response"] = f"{notice} Cart total: {self._price(calculate_cart_total(updated_cart))}"
        return state

    def _pending_subscription(self, service: SubscriptionService, customer_phone: str) -> CustomerSubscription | None:
        return service.get_pending_subscription(self._phone(customer_phone)) if self._phone(customer_phone) else None

    def _latest_subscription(self, service: SubscriptionService, customer_phone: str) -> CustomerSubscription | None:
        phone = self._phone(customer_phone)
        if not phone:
            return None
        stmt = select(CustomerSubscription).where(CustomerSubscription.customer_phone == phone).order_by(CustomerSubscription.created_at.desc())
        return service.db.scalars(stmt).first()

    def _capture_address(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        address = str(state.get("last_user_message", "")).strip()
        customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
        self.memory.save(conversation_id, address=address, customer_phone=customer_phone)
        state["address"] = address
        subscription_service = SubscriptionService(self.order_service.db)
        pending = self._pending_subscription(subscription_service, customer_phone)
        if pending is not None:
            pending.delivery_address = address
            subscription_service.db.commit()
            state["last_response"] = "I saved your delivery address for the pending subscription. Type 'confirm' when you want to continue."
        elif list(memory_state.get("cart", [])):
            state["last_response"] = "I saved your delivery address. Type 'confirm order' when you are ready to place the order."
        else:
            state["last_response"] = "I saved this as your delivery address. When you add a meal or choose a plan, I can use it for checkout."
        return state

    def _order_summary(self, order: Order) -> str:
        lines = [f"Order #: {order.order_number}"]
        lines.extend(f"{item.quantity} {chr(0x00D7)} {item.product.name} {chr(0x2014)} {self._price(item.subtotal)}" for item in order.items)
        lines.append(f"Total: {self._price(order.total_amount)}")
        lines.append(f"Status: {order.status.title()}")
        lines.append("")
        lines.append("You can type 'track my order' anytime to check its status.")
        return "\n".join(lines)

    def _confirm_order(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
        cart = list(memory_state.get("cart", []))
        address = str(memory_state.get("address") or "").strip()
        subscription_service = SubscriptionService(self.order_service.db)
        pending = self._pending_subscription(subscription_service, customer_phone)
        if pending is not None and not cart:
            if not pending.delivery_address:
                state["last_response"] = "Please share your delivery address before confirming the subscription."
                return state
            pending.status = "active"
            subscription_service.db.commit()
            plan = pending.plan or subscription_service.retrieve_subscription_plan(pending.subscription_plan_id)
            state["last_response"] = f"Your {plan.name if plan is not None else 'subscription'} is now active. Status: active."
            return state
        if not cart:
            state["last_response"] = "Your cart is empty. Add a meal before confirming your order."
            return state
        if not address:
            state["last_response"] = "Please provide your delivery address before confirming your order."
            return state
        if not customer_phone:
            state["last_response"] = "I need your phone number to place the order."
            return state
        try:
            order = self.order_service.create_draft_order(create_order_payload("", customer_phone, address, cart))
            confirmed = self.order_service.confirm_order(order.order_number)
        except Exception:
            logger.exception("order_confirmation_failed", extra={"event": "order_confirmation_failed", "conversation_id": conversation_id})
            state["last_response"] = "I could not place your order right now. Please try again shortly."
            return state
        self.memory.save(conversation_id, cart=[], address=address, order_number=confirmed.order_number, order_status=confirmed.status, customer_phone=customer_phone)
        state["cart"] = []
        state["order_number"] = confirmed.order_number
        state["order_status"] = confirmed.status
        state["last_response"] = "Your order has been placed successfully.\n" + self._order_summary(confirmed)
        return state

    def _modify_order(self, state: ConversationState) -> ConversationState:
        """Explain safe replacement of an already-placed customer order."""
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
        order = None
        remembered_number = str(memory_state.get("order_number") or "").strip()
        if customer_phone and remembered_number:
            order = self.order_service.retrieve_order_by_order_number(remembered_number, customer_phone=customer_phone)
        if order is None and customer_phone:
            order = self.order_service.retrieve_latest_order_for_customer(customer_phone)
        if order is None:
            state["last_response"] = "I could not find a recent customer order to modify. Please share the order number if you need help."
            return state
        non_cancellable = {"cancelled", "out_for_delivery", "delivered", "completed"}
        status_text = order.status.replace("_", " ")
        if order.status in non_cancellable:
            state["last_response"] = f"Your order {order.order_number} has already been placed with status {status_text}. I cannot edit its items. I cannot cancel this order now."
        else:
            state["last_response"] = f"Your order {order.order_number} has already been placed. I cannot edit its items directly. If it is still eligible for cancellation, I can cancel it so you can place a new one."
        state["order_number"] = order.order_number
        state["order_status"] = order.status
        return state

    def _track_order(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        order_number = extract_order_reference(str(state.get("last_user_message", ""))) or str(state.get("classified_order_number") or memory_state.get("order_number") or "")
        customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
        if not order_number and customer_phone:
            latest = self.order_service.retrieve_latest_order_for_customer(customer_phone)
            if latest is not None:
                order_number = latest.order_number
        if not order_number:
            state["last_response"] = "I do not have an order number to track yet. Please share the full order number, for example TF-260807-1042."
            return state
        order = (self.order_service.retrieve_order_by_order_number(order_number, customer_phone=customer_phone) if customer_phone else None)
        if order is None and not extract_order_reference(str(state.get("last_user_message", ""))) and customer_phone:
            order = self.order_service.retrieve_latest_order_for_customer(customer_phone)
        if order is None:
            state["last_response"] = f"I could not find order {order_number}."
            return state
        self.memory.save(conversation_id, order_number=order.order_number, order_status=order.status, customer_phone=state.get("customer_phone"))
        state["order_number"] = order.order_number
        state["order_status"] = order.status
        state["last_response"] = self._order_summary(order)
        return state

    def _cancel_order(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        order_number = extract_order_reference(str(state.get("last_user_message", ""))) or str(state.get("classified_order_number") or memory_state.get("order_number") or "")
        if not order_number:
            state["last_response"] = "Please share the order number you want to cancel."
            return state
        try:
            customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
            if not customer_phone or self.order_service.retrieve_order_by_order_number(order_number, customer_phone=customer_phone) is None:
                raise ValueError(f"Order {order_number} was not found.")
            order = self.order_service.cancel_order_for_customer(order_number, customer_phone)
        except ValueError as exc:
            state["last_response"] = str(exc)
            return state
        except Exception:
            logger.exception("order_cancellation_failed", extra={"event": "order_cancellation_failed", "order_number": order_number})
            state["last_response"] = "I could not cancel the order right now. Please try again shortly."
            return state
        self.memory.save(conversation_id, order_number=order.order_number, order_status=order.status, customer_phone=state.get("customer_phone"))
        state["order_number"] = order.order_number
        state["order_status"] = order.status
        state["last_response"] = f"Order {order.order_number} has been cancelled. Status: {order.status}."
        return state

    def _resolve_plan(self, message: str, state: ConversationState, service: SubscriptionService) -> Any | None:
        selected = state.get("pending_subscription_plan") if isinstance(state.get("pending_subscription_plan"), dict) else None
        if selected and selected.get("plan_id"):
            return service.retrieve_subscription_plan(int(selected["plan_id"]))
        normalized = normalize_text(message)
        plans = service.list_subscription_plans()
        position = extract_position_reference(message)
        if position is not None and position > 0 and position <= len(plans):
            return plans[position - 1]
        for plan in plans:
            plan_name = self.product_service.normalize_name(plan.name)
            if plan_name in normalized or normalized == plan_name:
                return plan
        return None

    def _plan_line(self, plan: Any, index: int) -> str:
        meals = ", ".join(str(meal).title() for meal in plan.included_meal_types)
        return f"{index}. {plan.name}: {meals}, {plan.number_of_days} days, {self._price(plan.price)}"

    async def _subscription(self, state: ConversationState) -> ConversationState:
        message = str(state.get("last_user_message", ""))
        intent = str(state.get("intent") or "fallback")
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        customer_phone = self._phone(state.get("customer_phone") or memory_state.get("customer_phone"))
        service = SubscriptionService(self.order_service.db)
        policy_service = TiffinPolicyService(self.order_service.db)
        today = date.today()
        if intent == "subscription_plans":
            plans = service.list_subscription_plans()
            if not plans:
                state["last_response"] = "Subscription plans are not available right now. Please contact support."
                return state
            state["displayed_options"] = [{"label": plan.name, "plan_id": plan.id} for plan in plans]
            state["displayed_context_type"] = "plans"
            lines = ["Available subscription plans:"]
            lines.extend(self._plan_line(plan, index) for index, plan in enumerate(plans, start=1))
            lines.append("")
            lines.append("Reply with the plan number or plan name to continue.")
            state["last_response"] = "\n".join(lines)
            return state
        if intent == "create_subscription":
            plan = self._resolve_plan(message, state, service)
            if plan is None:
                state["last_response"] = "Please tell me which subscription plan you want, or type 'subscription plans' to view the options."
                return state
            if not customer_phone:
                state["last_response"] = "I need your phone number before starting a subscription."
                return state
            pending = self._pending_subscription(service, customer_phone)
            if pending is None:
                pending = service.create_customer_subscription(customer_phone=customer_phone, subscription_plan_id=plan.id, start_date=today, end_date=today + timedelta(days=plan.number_of_days - 1), delivery_address=str(memory_state.get("address") or "") or None, preferred_meal_choices=[], payment_method=None, status="pending")
            else:
                pending.subscription_plan_id = plan.id
                pending.start_date = today
                pending.end_date = today + timedelta(days=plan.number_of_days - 1)
                if not pending.delivery_address and memory_state.get("address"):
                    pending.delivery_address = str(memory_state.get("address"))
                pending.status = "pending"
                service.db.commit()
            state["last_response"] = f"Selected plan: {plan.name}\nMeals: {', '.join(str(meal).title() for meal in plan.included_meal_types)}\nDuration: {plan.number_of_days} days\nPrice: {self._price(plan.price)}\n\nPlease share your delivery address if it is missing, then type 'confirm' to activate the subscription."
            return state
        latest = self._latest_subscription(service, customer_phone)
        if intent == "subscription_status":
            if latest is None:
                state["last_response"] = "You do not have an active or pending subscription right now."
                return state
            plan = latest.plan or service.retrieve_subscription_plan(latest.subscription_plan_id)
            meals = ", ".join(str(meal).title() for meal in getattr(plan, "included_meal_types", [])) or "Not available"
            state["last_response"] = f"Plan: {plan.name if plan is not None else 'Subscription'}\nStatus: {latest.status}\nMeal coverage: {meals}\nStart: {latest.start_date}\nEnd: {latest.end_date}"
            return state
        if latest is None:
            state["last_response"] = "You do not have a subscription to manage right now."
            return state
        if intent == "pause_subscription":
            if latest.status == "cancelled":
                state["last_response"] = "Cancelled subscriptions cannot be paused."
            else:
                state["last_response"] = "Your subscription has been paused." if service.pause_customer_subscription(customer_phone) is not None else "You do not have an active subscription to pause."
            return state
        if intent == "resume_subscription":
            if latest.status == "cancelled":
                state["last_response"] = "Cancelled subscriptions cannot be resumed."
            else:
                resumed = service.resume_customer_subscription(customer_phone, on_date=today)
                state["last_response"] = f"Your subscription has been resumed. Status: {resumed.status}." if resumed is not None else "You do not have a paused subscription to resume."
            return state
        if intent == "cancel_subscription":
            if latest.status == "cancelled":
                state["last_response"] = "Your subscription is already cancelled."
            else:
                state["last_response"] = "Your subscription has been cancelled." if service.cancel_customer_subscription(customer_phone) is not None else "You do not have a subscription to cancel right now."
            return state
        if intent == "skip_meal":
            if latest.status == "cancelled":
                state["last_response"] = "Cancelled subscriptions cannot be used for meal skips."
                return state
            active = service.get_active_subscription(customer_phone, on_date=today)
            if active is None:
                state["last_response"] = "You do not have an active subscription to skip meals from."
                return state
            meal_type = extract_meal_type(message)
            day_name = extract_day(message, base_date=today)
            if meal_type is None:
                state["last_response"] = "Please tell me which meal you want to skip, for example 'skip tomorrow lunch'."
                return state
            if day_name is None:
                state["last_response"] = "Please tell me which date you want to skip, for example 'skip tomorrow lunch' or 'skip Friday dinner'."
                return state
            target_date = next(today + timedelta(days=offset) for offset in range(8) if (today + timedelta(days=offset)).strftime("%A") == day_name)
            result = policy_service.validate_meal_skip(subscription=active, meal_date=target_date, meal_type=meal_type, reason=message)
            state["last_response"] = f"Your {meal_type} on {target_date.isoformat()} has been skipped." if result.is_valid else (result.reason or "I could not skip that meal.")
            return state
        state["last_response"] = f"Bulk orders for {BULK_ORDER_THRESHOLD} or more boxes need manual confirmation. Please share the delivery address, quantity, and meal details, and support will follow up." if intent == "bulk_order" else DEFAULT_REPLY
        return state

    async def _menu(self, state: ConversationState) -> ConversationState:
        message = str(state.get("last_user_message", ""))
        intent = str(state.get("intent") or "fallback")
        day = str(state.get("selected_menu_day") or state.get("classified_day") or extract_day(message, base_date=date.today()) or date.today().strftime("%A"))
        if intent == "today_menu":
            state["last_response"] = self._format_daily_menu(day)
        elif intent == "weekly_menu":
            text, options = self._format_weekly_menu()
            state["last_response"] = text
            if options:
                state["displayed_options"] = options
                state["displayed_context_type"] = "menu_day"
        else:
            state["last_response"] = self._format_daily_menu(day, meal_type=intent.replace("_menu", ""))
        return state
    async def _rag(self, state: ConversationState) -> ConversationState:
        try:
            state["last_response"] = self._reply(await self.rag_chain.ask(str(state.get("last_user_message", ""))) or POLICY_FALLBACK)
        except Exception:
            logger.exception("rag_query_failed", extra={"event": "rag_query_failed"})
            state["last_response"] = POLICY_FALLBACK
        return state

    def _payment_methods(self, state: ConversationState) -> ConversationState:
        state["last_response"] = "Payment methods: cash on delivery, online transfer, and bank transfer."
        return state

    def _human_handoff(self, state: ConversationState) -> ConversationState:
        state["last_response"] = "I cannot connect you to a live agent inside WhatsApp right now. Please contact TiffinAI support or ask the business owner to follow up."
        return state

    def _fallback(self, state: ConversationState) -> ConversationState:
        state["last_response"] = str(state.get("clarification_response") or DEFAULT_REPLY)
        return state

    def _compose_response(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        reply = self._reply(state.get("last_response"))
        messages = self._append_messages(state, memory_state, reply)
        self.memory.save(conversation_id, messages=messages, cart=state.get("cart", memory_state.get("cart", [])), address=state.get("address", memory_state.get("address")), order_number=state.get("order_number", memory_state.get("order_number")), order_status=state.get("order_status", memory_state.get("order_status")), customer_phone=state.get("customer_phone", memory_state.get("customer_phone")), last_response=reply)
        state["messages"] = messages
        state["last_response"] = reply
        return state

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ConversationState)
        workflow.add_node("route_intent", self._route_intent)
        workflow.add_node("greeting", self._greeting)
        workflow.add_node("menu", self._menu)
        workflow.add_node("add_item", self._add_item)
        workflow.add_node("remove_item", self._remove_item)
        workflow.add_node("change_quantity", self._change_quantity)
        workflow.add_node("clear_cart", self._clear_cart)
        workflow.add_node("view_cart", self._view_cart)
        workflow.add_node("search_menu", self._search_menu)
        workflow.add_node("provide_address", self._capture_address)
        workflow.add_node("confirm_order", self._confirm_order)
        workflow.add_node("track_order", self._track_order)
        workflow.add_node("cancel_order", self._cancel_order)
        workflow.add_node("modify_order", self._modify_order)
        workflow.add_node("subscription", self._subscription)
        workflow.add_node("rag", self._rag)
        workflow.add_node("payment_methods", self._payment_methods)
        workflow.add_node("human_handoff", self._human_handoff)
        workflow.add_node("fallback", self._fallback)
        workflow.add_node("compose_response", self._compose_response)
        workflow.set_entry_point("route_intent")
        workflow.add_conditional_edges("route_intent", lambda state: str(state.get("intent") or "fallback"), {"greeting": "greeting", "today_menu": "menu", "weekly_menu": "menu", "breakfast_menu": "menu", "lunch_menu": "menu", "dinner_menu": "menu", "add_item": "add_item", "remove_item": "remove_item", "change_quantity": "change_quantity", "clear_cart": "clear_cart", "view_cart": "view_cart", "search_menu": "search_menu", "provide_address": "provide_address", "confirm_order": "confirm_order", "track_order": "track_order", "cancel_order": "cancel_order", "modify_order": "modify_order", "subscription_plans": "subscription", "create_subscription": "subscription", "subscription_status": "subscription", "pause_subscription": "subscription", "resume_subscription": "subscription", "cancel_subscription": "subscription", "skip_meal": "subscription", "bulk_order": "subscription", "delivery_area": "rag", "delivery_timing": "rag", "payment_methods": "payment_methods", "faq": "rag", "human_handoff": "human_handoff", "fallback": "fallback"})
        for node in ("greeting", "menu", "add_item", "remove_item", "change_quantity", "clear_cart", "view_cart", "search_menu", "provide_address", "confirm_order", "track_order", "cancel_order", "modify_order", "subscription", "rag", "payment_methods", "human_handoff", "fallback"):
            workflow.add_edge(node, "compose_response")
        workflow.add_edge("compose_response", END)
        return workflow.compile()

    async def run(self, message: str, conversation_id: str = "default", customer_phone: str | None = None, message_id: str | None = None) -> dict[str, Any]:
        self.memory.clear_expired_cart(
            conversation_id,
            max_age=timedelta(minutes=max(1, int(settings.CART_INACTIVITY_MINUTES))),
        )
        memory_state = self._load_context(conversation_id)
        if message_id and self.memory.has_processed_message(conversation_id, message_id):
            return {"response": self._reply(memory_state.get("last_response")), "intent": "fallback", "cart": list(memory_state.get("cart", [])), "address": memory_state.get("address"), "order_number": memory_state.get("order_number"), "order_status": memory_state.get("order_status"), "messages": list(memory_state.get("messages", [])), "retrieved_context": ""}
        initial_state: ConversationState = {"classified_include_terms": [], "classified_exclude_terms": [], "messages": list(memory_state.get("messages", [])), "last_user_message": message, "cart": list(memory_state.get("cart", [])), "address": memory_state.get("address"), "order_number": memory_state.get("order_number"), "order_status": memory_state.get("order_status"), "conversation_id": conversation_id, "customer_phone": customer_phone or str(memory_state.get("customer_phone") or ""), "message_id": message_id, "retrieved_context": "", "error": None}
        result = await self.graph.ainvoke(initial_state)
        if message_id and not self.memory.has_processed_message(conversation_id, message_id):
            self.memory.mark_processed_message(conversation_id, message_id)
        return {"response": self._reply(result.get("last_response")), "intent": result.get("intent", "fallback"), "intent_source": result.get("intent_source", "fallback"), "intent_confidence": result.get("intent_confidence", 0.0), "cart": result.get("cart", []), "address": result.get("address"), "order_number": result.get("order_number"), "order_status": result.get("order_status"), "messages": result.get("messages", []), "retrieved_context": result.get("retrieved_context", "")}





























