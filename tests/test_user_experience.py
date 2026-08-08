from __future__ import annotations

import asyncio
import re
from decimal import Decimal

from app.langgraph.parsing import extract_order_reference, infer_intent
from app.langgraph.workflow import WELCOME_MESSAGE
from app.models.order import Order
from app.services.order_service import OrderService
from app.services.product_service import ProductService


def test_requested_natural_language_intents() -> None:
    cases = {
        "aaj menu mai kia hai": "today_menu",
        "friday ka menu": "today_menu",
        "meri cart mai kia hai": "view_cart",
        "cart dikhao": "view_cart",
        "mujhay anda chana order krna hai": "add_item",
        "mera order kahan hai": "track_order",
        "mujhay order cancel krna hai": "cancel_order",
        "monthly plan chahiye": "subscription_plans",
        "confirm order": "confirm_order",
    }
    assert {message: infer_intent(message) for message in cases} == cases


def test_welcome_message_is_natural_and_not_numbered() -> None:
    assert "Welcome to TiffinAI" in WELCOME_MESSAGE
    assert "What would you like to eat today?" in WELCOME_MESSAGE
    assert "1." not in WELCOME_MESSAGE
    assert "What's on today's menu?" in WELCOME_MESSAGE


def test_public_order_number_format_uniqueness_and_legacy_compatibility(db_session) -> None:
    products = ProductService(db_session)
    product = products.create_product(
        name="Public ID Meal",
        description="Test meal",
        price=Decimal("190.00"),
        is_available=True,
    )
    service = OrderService(db_session)
    payload = {
        "customer_phone": "15551234567",
        "delivery_address": "House 1, Main Road",
        "items": [{"product_id": product.id, "quantity": 1}],
    }

    first = service.create_draft_order(__import__("app.schemas.order", fromlist=["OrderCreate"]).OrderCreate(**payload))
    second = service.create_draft_order(__import__("app.schemas.order", fromlist=["OrderCreate"]).OrderCreate(**payload))

    assert re.fullmatch(r"TF-[0-9]{6}-[A-Z0-9]{4}", first.order_number)
    assert re.fullmatch(r"TF-[0-9]{6}-[A-Z0-9]{4}", second.order_number)
    assert first.order_number != second.order_number
    assert first.id != second.id
    assert extract_order_reference(first.order_number) == first.order_number

    legacy = Order(
        order_number="ORD-LEGACY-123",
        customer_phone="15551234567",
        delivery_address="House 2, Main Road",
        status="draft",
        total_amount=Decimal("0.00"),
    )
    db_session.add(legacy)
    db_session.commit()

    assert service.retrieve_order_by_order_number("ORD-LEGACY-123") is not None
    cancelled = service.cancel_order(first.order_number)
    assert cancelled.order_number == first.order_number
    assert cancelled.status == "cancelled"
    assert service.retrieve_order_by_order_number(first.order_number).status == "cancelled"


def test_workflow_cart_and_confirmation_use_compact_customer_format(workflow, customer_phone) -> None:
    conversation_id = "ux-format"
    added = asyncio.run(workflow.run("I want Anda Chana", conversation_id=conversation_id, customer_phone=customer_phone, message_id="ux-1"))
    assert "has been added to your cart" in added["response"]
    assert "Want to add anything else?" in added["response"]

    address = asyncio.run(workflow.run("ye address hai House 9, Main Road", conversation_id=conversation_id, customer_phone=customer_phone, message_id="ux-2"))
    assert address["intent"] == "provide_address"

    confirmed = asyncio.run(workflow.run("order confirm kro", conversation_id=conversation_id, customer_phone=customer_phone, message_id="ux-3"))
    assert "Order #: TF-" in confirmed["response"]
    assert "Status: Confirmed" in confirmed["response"]
    assert "track my order" in confirmed["response"]
def test_all_requested_natural_language_variants() -> None:
    cases = {
        "today's menu": "today_menu",
        "show today's menu": "today_menu",
        "aaj menu mai kia hai": "today_menu",
        "aaj ka menu": "today_menu",
        "what is in menu": "today_menu",
        "weekly menu": "weekly_menu",
        "is haftay ka menu": "weekly_menu",
        "Friday menu": "today_menu",
        "friday ka menu": "today_menu",
        "kal ka menu": "today_menu",
        "view cart": "view_cart",
        "show my cart": "view_cart",
        "what's in my cart": "view_cart",
        "meri cart mai kia hai": "view_cart",
        "cart dikhao": "view_cart",
        "mera cart": "view_cart",
        "cart check kro": "view_cart",
        "I want Anda Chana": "add_item",
        "add Anda Chana": "add_item",
        "mujhay anda chana order krna hai": "add_item",
        "anda chana cart mai add kro": "add_item",
        "I want Chicken Biryani": "add_item",
        "biryani order krni hai": "add_item",
        "track my order": "track_order",
        "order status": "track_order",
        "mera order kahan hai": "track_order",
        "mera order track kro": "track_order",
        "order ka status batao": "track_order",
        "cancel my order": "cancel_order",
        "cancel order": "cancel_order",
        "mujhay order cancel krna hai": "cancel_order",
        "mera order cancel kro": "cancel_order",
        "order cancel kar do": "cancel_order",
        "subscription plans": "subscription_plans",
        "show subscriptions": "subscription_plans",
        "monthly plan": "subscription_plans",
        "mujhay monthly plan chahiye": "subscription_plans",
        "subscription options dikhao": "subscription_plans",
        "confirm order": "confirm_order",
        "order confirm kro": "confirm_order",
        "ye address hai House 1, Main Road": "provide_address",
        "delivery address House 1, Main Road": "provide_address",
        "address save kro": "provide_address",
    }
    for message, expected in cases.items():
        assert infer_intent(message) == expected, message
def test_real_menu_cart_confirm_regression(workflow, customer_phone) -> None:
    conversation_id = "real-cart-confirm-regression"

    menu = asyncio.run(workflow.run("today's menu", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-1"))
    assert menu["intent"] == "today_menu"
    assert "Chicken Karahi" in menu["response"]

    added = asyncio.run(workflow.run("I want to order chicken karahi", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-2"))
    assert added["intent"] == "add_item"
    assert any(item["name"] == "Chicken Karahi" for item in added["cart"])

    cart = asyncio.run(workflow.run("what is in my cart?", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-3"))
    assert cart["intent"] == "view_cart"
    assert "Chicken Karahi" in cart["response"]
    assert "1 " in cart["response"]
    assert "Rs. 380.00" in cart["response"]

    confirmation = asyncio.run(workflow.run("order confirm", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-4"))
    assert confirmation["intent"] == "confirm_order"
    assert "delivery address" in confirmation["response"].lower()
    assert "meal in the menu" not in confirmation["response"].lower()

    address = asyncio.run(workflow.run("My address is House 12, Main Road", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-5"))
    assert address["intent"] == "provide_address"
    placed = asyncio.run(workflow.run("order confirm", conversation_id=conversation_id, customer_phone=customer_phone, message_id="real-6"))
    assert placed["intent"] == "confirm_order"
    assert "order has been placed successfully" in placed["response"].lower()


def test_command_precedence_does_not_turn_order_commands_into_meals() -> None:
    assert infer_intent("I want to order Chicken Karahi") == "add_item"
    assert infer_intent("order confirm") == "confirm_order"
    assert infer_intent("track order TF-260808-AB12") == "track_order"
    assert infer_intent("cancel order TF-260808-AB12") == "cancel_order"


def test_generic_fallback_does_not_mention_subscriptions(workflow) -> None:
    result = asyncio.run(workflow.run("something completely unrelated", conversation_id="fallback-copy"))
    assert "didn't quite understand" in result["response"]
    assert "subscriptions" not in result["response"].lower()
def test_cart_and_confirmation_roman_urdu_variants() -> None:
    cart_variants = [
        "cart dikhao",
        "mera cart dikhao",
        "meri cart dikhao",
        "cart mein kya hai",
        "cart me kya hai",
        "mere cart mein kya hai",
    ]
    confirm_variants = [
        "mera order confirm karo",
        "order confirm karo",
        "mera order place karo",
    ]
    assert all(infer_intent(message) == "view_cart" for message in cart_variants)
    assert all(infer_intent(message) == "confirm_order" for message in confirm_variants)