from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.core.logging import setup_logger
from app.langgraph.memory import ConversationMemory
from app.langgraph.parsing import (
    CANONICAL_INTENTS,
    extract_day,
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
from app.services.tiffin_service import BULK_ORDER_THRESHOLD, SubscriptionService, TiffinCatalogService, TiffinPolicyService

logger = setup_logger(__name__)
MEAL_TYPES = ("breakfast", "lunch", "dinner")
DEFAULT_REPLY = "I can help with today's menu, your cart, orders, subscriptions, and delivery policies. Try 'today menu', 'view cart', or 'subscription plans'."
POLICY_FALLBACK = "I could not find that information in the TiffinAI policy documents. Please contact support."


class OrderConversationWorkflow:
    def __init__(self, rag_chain: RAGChain, product_service: ProductService, order_service: OrderService, memory: ConversationMemory | None = None, meal_service: TiffinCatalogService | None = None) -> None:
        self.rag_chain = rag_chain
        self.product_service = product_service
        self.order_service = order_service
        self.memory = memory or ConversationMemory()
        self.meal_service = meal_service
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
        if not messages or messages[-1] != user_message:
            messages.append(user_message)
        messages.append(assistant_message)
        return messages

    def _message_options(self, messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        for message in reversed(messages):
            if message.get("role") == "assistant" and isinstance(message.get("options"), list):
                return str(message.get("context_type") or "") or None, list(message.get("options") or [])
        return None, []

    def _resolve_context_option(self, memory_state: dict[str, object], message: str) -> dict[str, Any] | None:
        context_type, options = self._message_options(list(memory_state.get("messages", [])))
        if not context_type or not options:
            return None
        position = extract_position_reference(message)
        if position is None:
            return None
        index = position - 1 if position > 0 else len(options) - 1
        return options[index] if 0 <= index < len(options) else None

    def _route_intent(self, state: ConversationState) -> ConversationState:
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        message = str(state.get("last_user_message", ""))
        intent = infer_intent(message)
        selected = self._resolve_context_option(memory_state, message)
        if selected is not None:
            context_type, _ = self._message_options(list(memory_state.get("messages", [])))
            if context_type == "plans":
                intent = "create_subscription"
                state["pending_subscription_plan"] = selected
            elif context_type == "menu":
                intent = "add_item"
                state["pending_menu_option"] = selected
        if intent == "fallback" and self._looks_like_address(message):
            has_checkout_context = bool(memory_state.get("cart")) or bool(memory_state.get("address"))
            has_subscription_context = bool(self._phone(state.get("customer_phone") or memory_state.get("customer_phone")))
            if has_checkout_context or has_subscription_context:
                intent = "provide_address"
        state["intent"] = intent if intent in CANONICAL_INTENTS else "fallback"
        return state

    def _greeting(self, state: ConversationState) -> ConversationState:
        state["last_response"] = "Assalam o Alaikum! Hello and welcome to TiffinAI.\n\nI can help you:\n1. View today's or weekly menu\n2. Add meals to your cart\n3. Place or track an order\n4. View or manage subscriptions\n5. Ask about delivery, payment, or policies\n\nWhat would you like to do?"
        return state

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
            return "\n".join(lines)
        items = self.meal_service.list_meals_for_day_and_type(day_name, meal_type)
        if not items:
            return f"No {meal_type} meals are available for {day_name} yet."
        lines = [f"{day_name} {meal_type} menu:"]
        lines.extend(f"- {item.name} ({self._price(item.price)})" for item in items)
        return "\n".join(lines)

    def _format_weekly_menu(self) -> tuple[str, list[dict[str, Any]]]:
        if self.meal_service is None:
            return "Weekly menu is not available yet. Please try again shortly.", []
        weekly_menu = self.meal_service.list_weekly_menu()
        lines = ["This week's menu:"]
        options: list[dict[str, Any]] = []
        has_items = False
        for day, day_menu in weekly_menu.items():
            day_lines: list[str] = []
            for meal_type in MEAL_TYPES:
                items = day_menu.get(meal_type, [])
                if items:
                    has_items = True
                    day_lines.append(f"{meal_type.title()}:")
                    day_lines.extend(f"- {item.name} ({self._price(item.price)})" for item in items)
                    options.extend({"label": item.name, "name": item.name} for item in items)
            if day_lines:
                lines.append(f"\n{day}:")
                lines.extend(day_lines)
        return ("\n".join(lines), options) if has_items else ("Weekly menu is not available yet. Please try again shortly.", [])

    def _resolve_products(self, message: str, pending_option: dict[str, Any] | None = None) -> list[Product]:
        if pending_option and pending_option.get("name"):
            product = self.product_service.retrieve_product_by_normalized_name(str(pending_option["name"]))
            return [product] if product is not None else []
        normalized = normalize_text(message)
        matches = [product for product in self.product_service.list_available_products() if self.product_service.normalize_name(product.name) in normalized]
        if matches:
            return matches
        exact = self.product_service.retrieve_product_by_normalized_name(message)
        return [exact] if exact is not None else []

    def _add_item(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        cart = list(memory_state.get("cart", []))
        pending_option = state.get("pending_menu_option") if isinstance(state.get("pending_menu_option"), dict) else None
        matches = self._resolve_products(str(state.get("last_user_message", "")), pending_option)
        if not matches:
            state["cart"] = cart
            state["last_response"] = "I could not find that meal in the menu. Type 'today menu' or 'weekly menu' to see available meals."
            return state
        if len(matches) > 1:
            state["cart"] = cart
            state["last_response"] = "I found more than one matching meal. Please reply with the exact meal name."
            return state
        product = matches[0]
        quantity = extract_quantity(str(state.get("last_user_message", ""))) or 1
        if quantity <= 0:
            state["cart"] = cart
            state["last_response"] = "Quantity must be greater than zero."
            return state
        subtotal = product.price * quantity
        updated_cart = [item for item in cart if int(item.get("product_id", 0)) != product.id]
        updated_cart.append({"product_id": product.id, "name": product.name, "quantity": quantity, "unit_price": str(product.price), "subtotal": str(subtotal)})
        self.memory.save(conversation_id, cart=updated_cart, customer_phone=state.get("customer_phone"))
        state["cart"] = updated_cart
        state["last_response"] = f"Added {quantity} x {product.name} to your cart.\nSubtotal: {self._price(subtotal)}\nType 'view cart' to review or 'confirm order' to continue."
        return state

    def _cart_line(self, item: dict[str, object]) -> str:
        subtotal = Decimal(str(item.get("subtotal") or Decimal(str(item.get("unit_price", 0))) * int(item.get("quantity", 0))))
        return f"- {int(item.get('quantity', 0))} x {item.get('name', 'Meal')} ({self._price(subtotal)})"

    def _view_cart(self, state: ConversationState) -> ConversationState:
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        cart = list(memory_state.get("cart", []))
        if not cart:
            state["cart"] = []
            state["last_response"] = "Your cart is empty. Type 'today menu' or 'weekly menu' to see available meals."
            return state
        lines = ["Your cart:"]
        lines.extend(self._cart_line(item) for item in cart)
        lines.append("")
        lines.append(f"Total: {self._price(calculate_cart_total(cart))}")
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
        target_index: int | None = None
        position = extract_position_reference(message)
        if position is not None and position > 0 and position <= len(cart):
            target_index = position - 1
        else:
            for index, item in enumerate(cart):
                if self.product_service.normalize_name(str(item.get("name", ""))) in message:
                    target_index = index
                    break
        if target_index is None:
            state["cart"] = cart
            state["last_response"] = "That meal is not in your cart. Type 'view cart' to review your items."
            return state
        target = dict(cart[target_index])
        remove_quantity = extract_quantity(message) or int(target.get("quantity", 1))
        updated_cart = list(cart)
        if remove_quantity >= int(target.get("quantity", 1)):
            updated_cart.pop(target_index)
            notice = f"Removed {target['name']} from your cart."
        else:
            remaining_quantity = int(target.get("quantity", 1)) - remove_quantity
            unit_price = Decimal(str(target.get("unit_price", 0)))
            updated_cart[target_index]["quantity"] = remaining_quantity
            updated_cart[target_index]["subtotal"] = str(unit_price * remaining_quantity)
            notice = f"Removed {remove_quantity} x {target['name']} from your cart."
        self.memory.save(conversation_id, cart=updated_cart, customer_phone=state.get("customer_phone"))
        state["cart"] = updated_cart
        if not updated_cart:
            state["last_response"] = f"{notice}\nYour cart is now empty."
            return state
        lines = [notice, "", "Updated cart:"]
        lines.extend(self._cart_line(item) for item in updated_cart)
        lines.append(f"Total: {self._price(calculate_cart_total(updated_cart))}")
        state["last_response"] = "\n".join(lines)
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
        lines = [f"Order number: {order.order_number}"]
        lines.extend(f"- {item.quantity} x {item.product.name} ({self._price(item.subtotal)})" for item in order.items)
        lines.append(f"Total: {self._price(order.total_amount)}")
        lines.append(f"Status: {order.status}")
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

    def _track_order(self, state: ConversationState) -> ConversationState:
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        order_number = extract_order_reference(str(state.get("last_user_message", ""))) or str(memory_state.get("order_number") or "")
        if not order_number:
            state["last_response"] = "I do not have an order number to track yet. Please share the full order number, for example ORD-123ABC."
            return state
        order = self.order_service.retrieve_order_by_order_number(order_number)
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
        order_number = extract_order_reference(str(state.get("last_user_message", ""))) or str(memory_state.get("order_number") or "")
        if not order_number:
            state["last_response"] = "Please share the order number you want to cancel."
            return state
        try:
            order = self.order_service.cancel_order(order_number)
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
        day = extract_day(message, base_date=date.today()) or date.today().strftime("%A")
        if intent == "today_menu":
            state["last_response"] = self._format_daily_menu(day)
        elif intent == "weekly_menu":
            text, options = self._format_weekly_menu()
            state["last_response"] = text
            if options:
                state["displayed_options"] = options
                state["displayed_context_type"] = "menu"
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
        state["last_response"] = DEFAULT_REPLY
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
        workflow.add_node("view_cart", self._view_cart)
        workflow.add_node("provide_address", self._capture_address)
        workflow.add_node("confirm_order", self._confirm_order)
        workflow.add_node("track_order", self._track_order)
        workflow.add_node("cancel_order", self._cancel_order)
        workflow.add_node("subscription", self._subscription)
        workflow.add_node("rag", self._rag)
        workflow.add_node("payment_methods", self._payment_methods)
        workflow.add_node("human_handoff", self._human_handoff)
        workflow.add_node("fallback", self._fallback)
        workflow.add_node("compose_response", self._compose_response)
        workflow.set_entry_point("route_intent")
        workflow.add_conditional_edges("route_intent", lambda state: str(state.get("intent") or "fallback"), {"greeting": "greeting", "today_menu": "menu", "weekly_menu": "menu", "breakfast_menu": "menu", "lunch_menu": "menu", "dinner_menu": "menu", "add_item": "add_item", "remove_item": "remove_item", "view_cart": "view_cart", "provide_address": "provide_address", "confirm_order": "confirm_order", "track_order": "track_order", "cancel_order": "cancel_order", "subscription_plans": "subscription", "create_subscription": "subscription", "subscription_status": "subscription", "pause_subscription": "subscription", "resume_subscription": "subscription", "cancel_subscription": "subscription", "skip_meal": "subscription", "bulk_order": "subscription", "delivery_area": "rag", "delivery_timing": "rag", "payment_methods": "payment_methods", "faq": "rag", "human_handoff": "human_handoff", "fallback": "fallback"})
        for node in ("greeting", "menu", "add_item", "remove_item", "view_cart", "provide_address", "confirm_order", "track_order", "cancel_order", "subscription", "rag", "payment_methods", "human_handoff", "fallback"):
            workflow.add_edge(node, "compose_response")
        workflow.add_edge("compose_response", END)
        return workflow.compile()

    async def run(self, message: str, conversation_id: str = "default", customer_phone: str | None = None, message_id: str | None = None) -> dict[str, Any]:
        memory_state = self._load_context(conversation_id)
        if message_id and self.memory.has_processed_message(conversation_id, message_id):
            return {"response": self._reply(memory_state.get("last_response")), "intent": "fallback", "cart": list(memory_state.get("cart", [])), "address": memory_state.get("address"), "order_number": memory_state.get("order_number"), "order_status": memory_state.get("order_status"), "messages": list(memory_state.get("messages", [])), "retrieved_context": ""}
        initial_state: ConversationState = {"messages": list(memory_state.get("messages", [])), "last_user_message": message, "cart": list(memory_state.get("cart", [])), "address": memory_state.get("address"), "order_number": memory_state.get("order_number"), "order_status": memory_state.get("order_status"), "conversation_id": conversation_id, "customer_phone": customer_phone or str(memory_state.get("customer_phone") or ""), "message_id": message_id, "retrieved_context": "", "error": None}
        result = await self.graph.ainvoke(initial_state)
        if message_id and not self.memory.has_processed_message(conversation_id, message_id):
            self.memory.mark_processed_message(conversation_id, message_id)
        return {"response": self._reply(result.get("last_response")), "intent": result.get("intent", "fallback"), "cart": result.get("cart", []), "address": result.get("address"), "order_number": result.get("order_number"), "order_status": result.get("order_status"), "messages": result.get("messages", []), "retrieved_context": result.get("retrieved_context", "")}


