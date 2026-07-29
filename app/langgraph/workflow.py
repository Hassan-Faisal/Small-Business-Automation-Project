from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from langgraph.graph import END, StateGraph
from decimal import Decimal
from app.langgraph.memory import ConversationMemory
from app.langgraph.parsing import extract_day, extract_meal_type, infer_intent
from app.langgraph.state import ConversationState
from app.langgraph.tools import (
    add_item_to_cart,
    build_menu_items,
    calculate_cart_total,
    create_order_payload,
    remove_item_from_cart,
)
from app.core.logging import setup_logger
from app.models.product import Product
from app.rag.rag_chain import RAGChain
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.tiffin_service import SubscriptionService, TiffinCatalogService, TiffinPolicyService, BULK_ORDER_THRESHOLD

logger = setup_logger(__name__)


class OrderConversationWorkflow:
    def __init__(
        self,
        rag_chain: RAGChain,
        product_service: ProductService,
        order_service: OrderService,
        memory: ConversationMemory | None = None,
        meal_service: TiffinCatalogService | None = None,
    ):
        self.rag_chain = rag_chain
        self.product_service = product_service
        self.order_service = order_service
        self.meal_service = meal_service
        self.memory = memory or ConversationMemory()
        self.graph = self._build_graph()

    def _resolve_product_from_message(
        self,
        message: str,
    ) -> Product | None:
        normalized_message = ProductService.normalize_name(message)
        available_products = (
            self.product_service.list_available_products()
        )

        for product in available_products:
            product_name = ProductService.normalize_name(
                product.name
            )

            if product_name in normalized_message:
                return product

        for product in available_products:
            product_name = ProductService.normalize_name(
                product.name
            )

            if normalized_message.startswith(product_name):
                return product

        return (
            self.product_service
            .retrieve_product_by_normalized_name(message)
        )

    def _extract_quantity(self, message: str) -> int:
        match = re.search(
            r"(?<!\d)(-?\d+)(?!\d)",
            message,
        )

        if match is None:
            return 1

        return int(match.group(1))

    def _extract_order_number(
        self,
        message: str,
    ) -> str | None:
        match = re.search(
            r"\bORD-[A-Z0-9]+(?:-[A-Z0-9]+)*\b",
            message.upper(),
        )

        return match.group(0) if match else None

    def _find_cart_item(
        self,
        cart: list[dict[str, object]],
        message: str,
    ) -> dict[str, object] | None:
        normalized_message = ProductService.normalize_name(
            message
        )

        for item in cart:
            item_name = ProductService.normalize_name(
                str(item.get("name", ""))
            )

            if item_name and item_name in normalized_message:
                return item

        for item in cart:
            item_name = ProductService.normalize_name(
                str(item.get("name", ""))
            )

            if normalized_message.startswith(item_name):
                return item

        return None

    def _load_context(
        self,
        conversation_id: str,
    ) -> dict[str, object]:
        return self.memory.get(conversation_id)

    def _append_messages(
        self,
        state: ConversationState,
        memory_state: dict[str, object],
        assistant_response: str,
    ) -> list[dict[str, str]]:
        messages = list(
            memory_state.get("messages", [])
        )

        user_message = {
            "role": "user",
            "content": str(
                state.get("last_user_message", "")
            ),
        }

        assistant_message = {
            "role": "assistant",
            "content": assistant_response,
        }
        displayed_options = state.get("displayed_options")
        if isinstance(displayed_options, list) and displayed_options:
            assistant_message["options"] = displayed_options
            assistant_message["context_type"] = str(state.get("displayed_context_type") or "")

        if not messages or messages[-1] != user_message:
            messages.append(user_message)

        messages.append(assistant_message)

        return messages

    @staticmethod
    def _select_position_index(message: str) -> int | None:
        normalized = ProductService.normalize_name(message)
        for word, index in {"first": 0, "second": 1, "third": 2, "last": -1}.items():
            if re.search(rf"\b{word}\b", normalized):
                return index
        match = re.search(r"(?<!\d)(\d+)(?!\d)", normalized)
        if match:
            value = int(match.group(1))
            return value - 1 if value > 0 else None
        return None

    @staticmethod
    def _get_message_options(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
        for message in reversed(messages):
            if message.get("role") == "assistant" and isinstance(message.get("options"), list):
                return str(message.get("context_type") or "" ) or None, list(message.get("options") or [])
        return None, []

    def _resolve_context_option(self, memory_state: dict[str, object], message: str) -> dict[str, Any] | None:
        _, options = self._get_message_options(list(memory_state.get("messages", [])))
        if not options:
            return None
        index = self._select_position_index(message)
        if index is None:
            return None
        if index < 0:
            index = len(options) + index
        if 0 <= index < len(options):
            return options[index]
        return None

    def _route_intent(
        self,
        state: ConversationState,
    ) -> ConversationState:
        message = str(
            state.get("last_user_message", "")
        )

        intent = infer_intent(message)
        memory_state = self._load_context(str(state.get("conversation_id", "default")))
        selected_option = self._resolve_context_option(memory_state, message)
        if selected_option is not None:
            context_type, _ = self._get_message_options(list(memory_state.get("messages", [])))
            if context_type == "plans":
                intent = "create_subscription"
                state["pending_subscription_plan"] = selected_option
            elif context_type == "menu":
                intent = "add_item"
                state["pending_menu_option"] = selected_option

        state["intent"] = intent
        state["needs_rag"] = intent == "business_question"

        return state

    def _greeting(
        self,
        state: ConversationState,
    ) -> ConversationState:
        state["last_response"] = (
            "Hello. I can help with the menu, your cart, "
            "delivery details, and orders."
        )

        return state

    def _show_menu(
        self,
        state: ConversationState,
    ) -> ConversationState:
        if self.meal_service is not None:
            weekly_menu = self.meal_service.list_weekly_menu()
            lines: list[str] = []
            for day, day_menu in weekly_menu.items():
                lines.append(f"{day}:")
                for meal_type in ("breakfast", "lunch", "dinner"):
                    items = day_menu.get(meal_type, [])
                    if not items:
                        continue
                    lines.append(f"{meal_type.title()}:")
                    for item in items:
                        lines.append(f"- {item.name} - Rs. {item.price}")
            menu_text = "\n".join(lines)
            state["retrieved_context"] = menu_text
            state["last_response"] = "Here is the current menu:\n\n" + menu_text
            state["displayed_options"] = [
                {"label": item.name, "product_id": item.id, "name": item.name, "price": str(item.price)}
                for meal_list in weekly_menu.values()
                for meal_items in meal_list.values()
                for item in meal_items
            ]
            state["displayed_context_type"] = "menu"
            return state

        products = self.product_service.list_available_products()

        if not products:
            state["retrieved_context"] = ""
            state["last_response"] = "The menu is currently unavailable."
            return state

        menu_items = build_menu_items(products)

        menu_lines = [f"- {item['name']} - Rs. {item['price']}" for item in menu_items]

        menu_text = "\n".join(menu_lines)

        state["retrieved_context"] = menu_text
        state["last_response"] = "Here is the current menu:\n\n" + menu_text

        return state


    def _add_item(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        message = str(
            state.get("last_user_message", "")
        )

        message_id = str(
            state.get("message_id") or ""
        )

        if (
            message_id
            and self.memory.has_processed_message(
                conversation_id,
                message_id,
            )
        ):
            state["last_response"] = str(
                memory_state.get("last_response")
                or "I already handled that message."
            )

            state["cart"] = list(
                memory_state.get("cart", [])
            )

            return state

        product = self._resolve_product_from_message(message)
        if product is None:
            pending_option = state.get("pending_menu_option")
            if isinstance(pending_option, dict) and pending_option.get("product_id"):
                product = self.product_service.retrieve_product_by_id(int(pending_option["product_id"]))
        if product is None:
            state["last_response"] = (
                "I couldn't find that product "
                "in the menu."
            )
            return state

        quantity = self._extract_quantity(message)

        if quantity <= 0:
            state["last_response"] = (
                "Quantity must be greater than zero."
            )
            return state

        cart = list(
            memory_state.get("cart", [])
        )

        updated_cart = add_item_to_cart(
            cart,
            product,
            quantity,
        )

        self.memory.save(
            conversation_id,
            cart=updated_cart,
            customer_phone=state.get(
                "customer_phone"
            ),
        )

        state["cart"] = updated_cart
        state["last_response"] = (
            f"Added {quantity} x {product.name} "
            "to your cart."
        )

        if message_id:
            self.memory.mark_processed_message(
                conversation_id,
                message_id,
            )

        return state

    def _remove_item(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        message = str(
            state.get("last_user_message", "")
        )

        message_id = str(
            state.get("message_id") or ""
        )

        if (
            message_id
            and self.memory.has_processed_message(
                conversation_id,
                message_id,
            )
        ):
            state["last_response"] = str(
                memory_state.get("last_response")
                or "I already handled that message."
            )

            state["cart"] = list(
                memory_state.get("cart", [])
            )

            return state

        cart = list(
            memory_state.get("cart", [])
        )

        if not cart:
            state["last_response"] = (
                "Your cart is empty."
            )
            return state

        item = self._find_cart_item(
            cart,
            message,
        )

        if item is None:
            state["last_response"] = (
                "I couldn't find that product "
                "in your cart."
            )
            return state

        updated_cart = remove_item_from_cart(
            cart,
            int(item["product_id"]),
        )

        self.memory.save(
            conversation_id,
            cart=updated_cart,
            customer_phone=state.get(
                "customer_phone"
            ),
        )

        state["cart"] = updated_cart
        state["last_response"] = (
            f"Removed {item['name']} "
            "from your cart."
        )

        if message_id:
            self.memory.mark_processed_message(
                conversation_id,
                message_id,
            )

        return state

    def _view_cart(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        cart = list(
            memory_state.get("cart", [])
        )

        if not cart:
            state["last_response"] = (
                "Your cart is empty."
            )
            state["cart"] = []
            state["retrieved_context"] = ""
            return state

        cart_lines = []

        for item in cart:
            quantity = int(
                item.get("quantity", 0)
            )

            name = str(
                item.get("name", "Unknown item")
            )

            subtotal = item.get("subtotal")

            if subtotal is None:
                unit_price = Decimal(
                    str(
                        item.get(
                            "unit_price",
                            item.get("price", 0),
                        )
                    )
                )

                subtotal = quantity * unit_price

            cart_lines.append(
                f"- {quantity} x {name} "
                f"— Rs. {subtotal:.2f}"
            )

        cart_text = "\n".join(cart_lines)
        total = calculate_cart_total(cart)

        state["cart"] = cart
        state["retrieved_context"] = cart_text
        state["last_response"] = (
            "Your cart contains:\n\n"
            f"{cart_text}\n\n"
            f"Total: Rs. {Decimal(str(total)):.2f}"
        )

        return state

    def _capture_address(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        address = str(
            state.get("last_user_message", "")
        ).strip()

        self.memory.save(
            conversation_id,
            address=address,
            customer_phone=state.get(
                "customer_phone"
            ),
        )

        state["address"] = address
        state["last_response"] = (
            "Thanks, I have your address."
        )

        return state

    def _confirm_order(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        message_id = str(
            state.get("message_id") or ""
        )

        if (
            message_id
            and self.memory.has_processed_message(
                conversation_id,
                message_id,
            )
        ):
            state["last_response"] = str(
                memory_state.get("last_response")
                or "Your order has already been confirmed."
            )

            state["order_number"] = (
                memory_state.get("order_number")
            )

            state["order_status"] = (
                memory_state.get("order_status")
            )

            return state

        cart = list(
            memory_state.get("cart", [])
        )

        if not cart:
            state["last_response"] = (
                "Your cart is empty, so there is "
                "nothing to confirm."
            )
            return state

        address = str(
            memory_state.get("address") or ""
        )

        if not address:
            state["last_response"] = (
                "Please provide your delivery address "
                "before confirming."
            )
            return state

        customer_phone = str(
            state.get("customer_phone")
            or memory_state.get("customer_phone")
            or ""
        )

        if not customer_phone:
            state["last_response"] = (
                "A customer phone number is required "
                "to place the order."
            )
            return state

        existing_order_number = str(
            memory_state.get("order_number") or ""
        )

        if existing_order_number:
            order = (
                self.order_service
                .retrieve_order_by_order_number(
                    existing_order_number
                )
            )
        else:
            order_payload = create_order_payload(
                "",
                customer_phone,
                address,
                cart,
            )

            order = (
                self.order_service
                .create_draft_order(order_payload)
            )

        if order is None:
            state["last_response"] = (
                "I couldn't create your order."
            )
            return state

        if order.status != "confirmed":
            confirmed = (
                self.order_service.confirm_order(
                    order.order_number
                )
            )
        else:
            confirmed = order

        self.memory.save(
            conversation_id,
            cart=cart,
            address=address,
            order_number=confirmed.order_number,
            order_status=confirmed.status,
            customer_phone=customer_phone,
        )

        state["order_number"] = (
            confirmed.order_number
        )

        state["order_status"] = (
            confirmed.status
        )

        state["last_response"] = (
            f"Your order {confirmed.order_number} "
            "has been confirmed. "
            f"Total: {confirmed.total_amount}."
        )

        if message_id:
            self.memory.mark_processed_message(
                conversation_id,
                message_id,
            )

        return state

    def _track_order(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        message = str(
            state.get("last_user_message", "")
        )

        explicit_order_number = (
            self._extract_order_number(message)
        )

        order_number = (
            explicit_order_number
            or str(
                memory_state.get("order_number") or ""
            )
        )

        if not order_number:
            state["last_response"] = (
                "I don't have an order number "
                "to track yet."
            )
            return state

        order = (
            self.order_service
            .retrieve_order_by_order_number(
                order_number
            )
        )

        if order is None:
            state["last_response"] = (
                f"I couldn't find order {order_number}."
            )
            return state

        self.memory.save(
            conversation_id,
            order_number=order.order_number,
            order_status=order.status,
            customer_phone=state.get(
                "customer_phone"
            ),
        )

        state["order_number"] = (
            order.order_number
        )

        state["order_status"] = (
            order.status
        )

        state["last_response"] = (
            f"Your order {order.order_number} "
            f"status is {order.status}."
        )

        return state

    @staticmethod
    def _normalize_response_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("reply_text", "response", "message", "content", "text"):
                nested = value.get(key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
                if isinstance(nested, dict):
                    nested_text = OrderConversationWorkflow._normalize_response_text(nested)
                    if nested_text:
                        return nested_text
        response_attr = getattr(value, "response", None)
        if isinstance(response_attr, str):
            return response_attr.strip()
        content_attr = getattr(value, "content", None)
        if isinstance(content_attr, str):
            return content_attr.strip()
        return str(value).strip()

    def _fallback(
        self,
        state: ConversationState,
    ) -> ConversationState:
        state["last_response"] = (
            "I can help with menus, cart updates, "
            "delivery details, and order tracking."
        )

        return state

    async def _handle_rag(
        self,
        state: ConversationState,
    ) -> ConversationState:
        message = str(
            state.get("last_user_message", "")
        )

        response = await self.rag_chain.ask(message)

        state["last_response"] = self._normalize_response_text(response)

        return state

    def _compose_response(
        self,
        state: ConversationState,
    ) -> ConversationState:
        conversation_id = str(
            state.get("conversation_id", "default")
        )

        memory_state = self._load_context(
            conversation_id
        )

        response = self._normalize_response_text(state.get("last_response"))

        message_id = str(
            state.get("message_id") or ""
        )

        messages = self._append_messages(
            state,
            memory_state,
            response,
        )

        self.memory.save(
            conversation_id,
            messages=messages,
            cart=state.get(
                "cart",
                memory_state.get("cart", []),
            ),
            address=state.get(
                "address",
                memory_state.get("address"),
            ),
            order_number=state.get(
                "order_number",
                memory_state.get("order_number"),
            ),
            order_status=state.get(
                "order_status",
                memory_state.get("order_status"),
            ),
            customer_phone=state.get(
                "customer_phone",
                memory_state.get("customer_phone"),
            ),
            last_response=response,
        )

        if (
            message_id
            and not self.memory.has_processed_message(
                conversation_id,
                message_id,
            )
        ):
            self.memory.mark_processed_message(
                conversation_id,
                message_id,
            )

        state["messages"] = messages

        return state

    def _format_weekly_menu(self) -> str:
        if self.meal_service is None:
            return "The menu is currently unavailable."

        weekly_menu = self.meal_service.list_weekly_menu()
        lines: list[str] = []
        for day, day_menu in weekly_menu.items():
            lines.append(f"{day}:")
            for meal_type in ("breakfast", "lunch", "dinner"):
                items = day_menu.get(meal_type, [])
                if not items:
                    continue
                lines.append(f"{meal_type.title()}:")
                for item in items:
                    lines.append(f"- {item.name} - Rs. {item.price}")
        return "\n".join(lines)

    def _format_daily_menu(self, day_of_week: str, meal_type: str | None = None) -> str:
        if self.meal_service is None:
            return "The menu is currently unavailable."

        if meal_type is None:
            menu = self.meal_service.list_daily_menu(day_of_week)
            meal_types = ("breakfast", "lunch", "dinner")
        else:
            menu = {meal_type: self.meal_service.list_meals_for_day_and_type(day_of_week, meal_type)}
            meal_types = (meal_type,)

        lines: list[str] = [f"{day_of_week.strip().title()} menu:"]
        for item_type in meal_types:
            items = menu.get(item_type, [])
            if not items:
                continue
            lines.append(f"{item_type.title()}:")
            for item in items:
                lines.append(f"- {item.name} - Rs. {item.price}")
        return "\n".join(lines)

    def _find_meal_by_name(self, message: str, meal_type: str | None = None) -> Any | None:
        if self.meal_service is None: 
            return None
        normalized = ProductService.normalize_name(message)
        offerings = self.meal_service.list_meal_offerings(active_only=True, meal_type=meal_type)
        for offering in offerings:
            if ProductService.normalize_name(offering.name) in normalized:
                return offering
        return None

    def _resolve_menu_day(
        self,
        message: str,
        default_day: str | None = None,
    ) -> str:
        lower = message.lower().strip()

        weekday_aliases = {
            "monday": {
                "monday",
                "mon",
                "peer",
                "pir",
                "somwar",
            },
            "tuesday": {
                "tuesday",
                "tue",
                "mangal",
                "mangalwar",
            },
            "wednesday": {
                "wednesday",
                "wed",
                "budh",
                "budhwar",
            },
            "thursday": {
                "thursday",
                "thu",
                "jumeraat",
                "jumerat",
            },
            "friday": {
                "friday",
                "fri",
                "jumma",
                "juma",
            },
            "saturday": {
                "saturday",
                "sat",
                "hafta",
            },
            "sunday": {
                "sunday",
                "sun",
                "itwar",
                "aitwar",
            },
        }

        for canonical_day, aliases in weekday_aliases.items():
            for alias in aliases:
                if re.search(
                    rf"\b{re.escape(alias)}\b",
                    lower,
                ):
                    return canonical_day.title()

        if any(
            phrase in lower
            for phrase in {
                "kal",
                "tomorrow",
                "next day",
                "agle din",
            }
        ):
            return (
                datetime.now(timezone.utc)
                + timedelta(days=1)
            ).strftime("%A")

        if any(
            phrase in lower
            for phrase in {
                "aaj",
                "today",
                "aj",
            }
        ):
            return datetime.now(
                timezone.utc
            ).strftime("%A")

        if default_day is not None:
            return default_day.strip().title()

        return datetime.now(
            timezone.utc
        ).strftime("%A")

    async def _handle_tiffin_domain(self, state: ConversationState) -> ConversationState:
        message = str(state.get("last_user_message", "")).strip()
        intent = str(state.get("intent") or "fallback")
        conversation_id = str(state.get("conversation_id", "default"))
        memory_state = self._load_context(conversation_id)
        lower = message.lower()
        subscription_service = SubscriptionService(self.order_service.db)
        policy_service = TiffinPolicyService(self.order_service.db)

        def set_response(text: str) -> ConversationState:
            state["last_response"] = text
            state["retrieved_context"] = text
            return state

        if intent == "menu":
            day = extract_day(message)
            meal_type = extract_meal_type(message)
            if day is not None and meal_type is not None:
                return set_response(self._format_daily_menu(day, meal_type=meal_type))
            if day is not None:
                return set_response(self._format_daily_menu(day))
            return set_response(self._format_weekly_menu())

        if intent == "today_menu":
            return set_response(self._format_daily_menu(self._resolve_menu_day(message)))

        if intent == "weekly_menu":
            return set_response(self._format_weekly_menu())

        if intent in {"breakfast_menu", "lunch_menu", "dinner_menu"}:
            meal_type = intent.replace("_menu", "")
            return set_response(self._format_daily_menu(self._resolve_menu_day(message), meal_type=meal_type))

        if intent == "meal_price":
            offering = self._find_meal_by_name(message)
            if offering is None:
                return set_response("I could not find that meal in today's menu.")
            return set_response(f"{offering.name} is Rs. {offering.price}.")

        if intent == "subscription_plans":
            plans = subscription_service.list_subscription_plans()
            lines = ["Available plans:"]
            for plan in plans:
                lines.append(f"- {plan.name} - Rs. {plan.price}")
            state["displayed_options"] = [{"label": plan.name, "plan_id": plan.id, "name": plan.name, "price": str(plan.price), "days": plan.number_of_days} for plan in plans]
            state["displayed_context_type"] = "plans"
            return set_response("\n".join(lines))

        if intent == "create_subscription":
            pending_plan = state.get("pending_subscription_plan")
            matched_plan = None
            if isinstance(pending_plan, dict) and pending_plan.get("plan_id"):
                matched_plan = subscription_service.retrieve_subscription_plan(int(pending_plan["plan_id"]))
            if matched_plan is None:
                for plan in subscription_service.list_subscription_plans():
                    if ProductService.normalize_name(plan.name) in ProductService.normalize_name(message):
                        matched_plan = plan
                        break
            if matched_plan is None:
                return set_response("Please tell me which subscription plan you want.")
            pending = getattr(self, "_pending_subscriptions", {})
            pending[conversation_id] = {
                "plan_id": matched_plan.id,
                "plan_name": matched_plan.name,
                "address": None,
                "payment_method": None,
            }
            self._pending_subscriptions = pending
            return set_response(
                f"{matched_plan.name} costs Rs. {matched_plan.price}. "
                "Please share your delivery address and preferred payment method to continue."
            )

        if intent == "subscribe":
            plans = subscription_service.list_subscription_plans()
            matched_plan = None
            pending_plan = state.get("pending_subscription_plan")
            if isinstance(pending_plan, dict) and pending_plan.get("plan_id"):
                matched_plan = subscription_service.retrieve_subscription_plan(int(pending_plan["plan_id"]))
            if matched_plan is None:
                for plan in plans:
                    if ProductService.normalize_name(plan.name) in ProductService.normalize_name(message):
                        matched_plan = plan
                        break
            if matched_plan is None:
                return set_response("Please tell me which subscription plan you want.")
            pending = getattr(self, "_pending_subscriptions", {})
            pending[conversation_id] = {"plan_id": matched_plan.id, "plan_name": matched_plan.name, "address": None, "payment_method": None}
            self._pending_subscriptions = pending
            return set_response(f"{matched_plan.name} costs Rs. {matched_plan.price}. Please share your delivery address and preferred payment method to continue.")

        if intent == "subscription_status":
            customer_phone = str(state.get("customer_phone") or memory_state.get("customer_phone") or "")
            context = subscription_service.get_customer_subscription_context(customer_phone)
            if not context.get("has_active_subscription"):
                return set_response("You do not have an active subscription yet.")
            included = ", ".join(context.get("included_meals_today", [])) or "no meals"
            return set_response(f"Your subscription is {context['status']} from {context['start_date']} to {context['end_date']}. Today's meals: {included}.")

        if intent == "skip_meal":
            customer_phone = str(state.get("customer_phone") or memory_state.get("customer_phone") or "")
            active = subscription_service.get_active_subscription(customer_phone)
            if active is None:
                return set_response("You do not have an active subscription to skip meals from.")
            meal_type = next((m for m in ("breakfast", "lunch", "dinner") if m in lower), "lunch")
            target_date = datetime.now(timezone.utc).date() + (timedelta(days=1) if "tomorrow" in lower else timedelta(days=0))
            result = policy_service.validate_meal_skip(subscription=active, meal_date=target_date, meal_type=meal_type, reason=message)
            if not result.is_valid:
                return set_response(result.reason or "Meal skip rejected.")
            return set_response(f"Your {meal_type} on {target_date} has been skipped.")

        if intent == "bulk_order":
            box_match = re.search(r"(?<!\d)(\d{1,3})(?!\d)", lower)
            number_of_boxes = int(box_match.group(1)) if box_match else BULK_ORDER_THRESHOLD
            requested_at = datetime.now(timezone.utc) + timedelta(days=1)
            result = policy_service.validate_bulk_order(requested_delivery_at=requested_at, number_of_boxes=number_of_boxes)
            if not result.is_valid:
                return set_response(result.reason or "Bulk order rejected.")
            return set_response(f"Bulk order noted for {number_of_boxes} boxes. Please share the delivery address and meal details.")

        if intent == "payment_methods":
            return set_response("Supported payment methods are cash on delivery, online transfer, and bank transfer.")

        if intent in {"delivery_area", "delivery_timing", "faq"}:
            response = await self.rag_chain.ask(message)
            return set_response(self._normalize_response_text(response) or "I could not find that information right now.")

        if intent == "human_handoff":
            return set_response("The owner will follow up with you shortly.")

        if intent == "provide_address":
            address = message.strip()
            self.memory.save(conversation_id, address=address, customer_phone=state.get("customer_phone"))
            state["address"] = address
            pending = getattr(self, "_pending_subscriptions", {}).get(conversation_id) if hasattr(self, "_pending_subscriptions") else None
            if pending is not None:
                pending["address"] = address
                return set_response("Thanks. Please share your payment method so I can activate your subscription.")
            return set_response("Thanks, I have your address.")

        if intent == "confirm_order":
            pending = getattr(self, "_pending_subscriptions", {}).get(conversation_id) if hasattr(self, "_pending_subscriptions") else None
            if pending is not None:
                customer_phone = str(state.get("customer_phone") or memory_state.get("customer_phone") or "")
                address = pending.get("address") or str(memory_state.get("address") or "")
                if not address:
                    return set_response("Please provide your delivery address before confirming your subscription.")
                payment_method = pending.get("payment_method") or "cash_on_delivery"
                plan = subscription_service.retrieve_subscription_plan(int(pending["plan_id"]))
                if plan is None:
                    return set_response("I could not find that subscription plan.")
                today = datetime.now(timezone.utc).date()
                subscription_service.create_customer_subscription(
                    customer_phone=customer_phone,
                    subscription_plan_id=plan.id,
                    start_date=today,
                    end_date=today + timedelta(days=plan.number_of_days - 1),
                    delivery_address=address,
                    preferred_meal_choices=[],
                    payment_method=payment_method,
                    status="active",
                )
                self._pending_subscriptions.pop(conversation_id, None)
                return set_response(f"Your subscription {plan.name} is now active.")
            return self._confirm_order(state)

        if intent == "add_meal":
            return self._add_item(state)

        if intent == "remove_meal":
            return self._remove_item(state)

        if intent == "update_quantity":
            memory_cart = list(memory_state.get("cart", []))
            if not memory_cart:
                return set_response("Your cart is empty.")
            new_quantity = self._extract_quantity(message)
            if new_quantity <= 0:
                return set_response("Quantity must be greater than zero.")
            target = self._find_cart_item(memory_cart, message) or memory_cart[-1]
            target["quantity"] = new_quantity
            unit_price = Decimal(str(target.get("unit_price", target.get("price", 0))))
            target["subtotal"] = unit_price * new_quantity
            self.memory.save(conversation_id, cart=memory_cart, customer_phone=state.get("customer_phone"))
            state["cart"] = memory_cart
            return set_response(f"Updated {target['name']} to {new_quantity}.")

        if intent == "cancel_order":
            return set_response("Your request has been noted. The owner will follow up about cancellation.")

        return state

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(
            ConversationState
        )

        workflow.add_node(
            "route_intent",
            self._route_intent,
        )

        workflow.add_node(
            "greeting",
            self._greeting,
        )

        workflow.add_node(
            "menu",
            self._show_menu,
        )

        workflow.add_node(
            "add_item",
            self._add_item,
        )

        workflow.add_node(
            "remove_item",
            self._remove_item,
        )

        workflow.add_node(
            "view_cart",
            self._view_cart,
        )

        workflow.add_node(
            "address",
            self._capture_address,
        )

        workflow.add_node(
            "confirm_order",
            self._confirm_order,
        )

        workflow.add_node(
            "track_order",
            self._track_order,
        )

        workflow.add_node(
            "rag",
            self._handle_rag,
        )

        workflow.add_node(
            "tiffin_domain",
            self._handle_tiffin_domain,
        )

        workflow.add_node(
            "fallback",
            self._fallback,
        )

        workflow.add_node(
            "compose_response",
            self._compose_response,
        )

        workflow.set_entry_point(
            "route_intent"
        )

        workflow.add_conditional_edges(
            "route_intent",
            lambda state: str(
                state.get("intent") or "fallback"
            ),
            {
                "greeting": "greeting",
                "today_menu": "tiffin_domain",
                "weekly_menu": "tiffin_domain",
                "menu": "tiffin_domain",
                "breakfast_menu": "tiffin_domain",
                "lunch_menu": "tiffin_domain",
                "dinner_menu": "tiffin_domain",
                "meal_price": "tiffin_domain",
                "add_item": "add_item",
                "add_meal": "add_item",
                "remove_item": "remove_item",
                "remove_meal": "remove_item",
                "update_order": "tiffin_domain",
                "update_quantity": "tiffin_domain",
                "view_cart": "view_cart",
                "delivery_area": "tiffin_domain",
                "delivery_timing": "tiffin_domain",
                "create_subscription": "tiffin_domain",
                "subscription_plans": "tiffin_domain",
                "subscribe": "tiffin_domain",
                "subscribe": "tiffin_domain",
                "subscription_status": "tiffin_domain",
                "skip_meal": "tiffin_domain",
                "bulk_order": "tiffin_domain",
                "payment_methods": "tiffin_domain",
                "provide_address": "tiffin_domain",
                "confirm_order": "confirm_order",
                "track_order": "track_order",
                "cancel_order": "tiffin_domain",
                "faq": "tiffin_domain",
                "human_escalation": "tiffin_domain",
                "human_handoff": "tiffin_domain",
                "human_handoff": "tiffin_domain",
                "business_question": "rag",
                "fallback": "fallback",
            },
        )

        terminal_nodes = [
            "greeting",
            "tiffin_domain",
            "menu",
            "add_item",
            "remove_item",
            "view_cart",
            "address",
            "confirm_order",
            "track_order",
            "rag",
            "fallback",
        ]

        for node in terminal_nodes:
            workflow.add_edge(
                node,
                "compose_response",
            )

        workflow.add_edge(
            "compose_response",
            END,
        )

        return workflow.compile()

    async def run(
        self,
        message: str,
        conversation_id: str = "default",
        customer_phone: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "workflow_execution_started",
            extra={
                "event": "workflow_execution_started",
                "conversation_id": conversation_id,
                "message_id": message_id,
            },
        )
        memory_state = self._load_context(
            conversation_id
        )

        current_phone = (
            customer_phone
            or str(
                memory_state.get(
                    "customer_phone"
                )
                or ""
            )
        )

        if (
            message_id
            and self.memory.has_processed_message(
                conversation_id,
                message_id,
            )
        ):
            logger.info(
                "workflow_duplicate_message",
                extra={
                    "event": "workflow_duplicate_message",
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                },
            )
            return {
                "response": str(
                    memory_state.get(
                        "last_response"
                    )
                    or ""
                ),
                "intent": "fallback",
                "cart": list(
                    memory_state.get("cart", [])
                ),
                "address": memory_state.get(
                    "address"
                ),
                "order_number": memory_state.get(
                    "order_number"
                ),
                "order_status": memory_state.get(
                    "order_status"
                ),
                "messages": list(
                    memory_state.get(
                        "messages",
                        [],
                    )
                ),
                "retrieved_context": "",
            }

        initial_state: ConversationState = {
            "messages": list(
                memory_state.get("messages", [])
            ),
            "last_user_message": message,
            "cart": list(
                memory_state.get("cart", [])
            ),
            "address": memory_state.get(
                "address"
            ),
            "order_number": memory_state.get(
                "order_number"
            ),
            "order_status": memory_state.get(
                "order_status"
            ),
            "conversation_id": conversation_id,
            "customer_phone": current_phone,
            "message_id": message_id,
            "retrieved_context": "",
            "error": None,
        }

        result = await self.graph.ainvoke(
            initial_state
        )

        logger.info(
            "workflow_execution_completed",
            extra={
                "event": "workflow_execution_completed",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "intent": result.get("intent", "fallback"),
            },
        )

        return {
            "response": result.get(
                "last_response",
                "",
            ),
            "intent": result.get(
                "intent",
                "fallback",
            ),
            "cart": result.get(
                "cart",
                [],
            ),
            "address": result.get(
                "address"
            ),
            "order_number": result.get(
                "order_number"
            ),
            "order_status": result.get(
                "order_status"
            ),
            "messages": result.get(
                "messages",
                [],
            ),
            "retrieved_context": result.get(
                "retrieved_context",
                "",
            ),
        }




