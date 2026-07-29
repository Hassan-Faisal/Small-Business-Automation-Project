from __future__ import annotations

import asyncio
import tempfile
from contextlib import suppress
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.langgraph.memory import ConversationMemory
from app.langgraph.workflow import OrderConversationWorkflow
from app.services.order_service import OrderService
from app.services.product_service import ProductService


def build_workflow():
    temp_dir = tempfile.TemporaryDirectory(prefix="graph-test-")
    db_path = Path(temp_dir.name) / "graph.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()

    product_service = ProductService(session)
    burger = product_service.create_product(name="Burger", description="Classic", price=Decimal("10.00"), is_available=True)
    fries = product_service.create_product(name="Fries", description="Side", price=Decimal("5.50"), is_available=True)
    soup = product_service.create_product(name="Soup", description="Unavailable", price=Decimal("4.00"), is_available=False)

    async def fake_rag(message: str) -> str:
        return f"policy response: {message}"

    rag_chain = SimpleNamespace(ask=fake_rag)
    order_service = OrderService(session)
    workflow = OrderConversationWorkflow(
        rag_chain=rag_chain,  # type: ignore[arg-type]
        product_service=product_service,
        order_service=order_service,
        memory=ConversationMemory(session),
    )

    def cleanup() -> None:
        with suppress(Exception):
            session.close()
        with suppress(Exception):
            engine.dispose()
        temp_dir.cleanup()

    return workflow, burger, fries, soup, order_service, session, cleanup


def test_customer_journey_and_edge_cases():
    workflow, burger, fries, soup, order_service, session, cleanup = build_workflow()
    conversation_id = "conv-1"
    try:
        greeting = asyncio.run(workflow.run("Hello", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-1"))
        assert "hello" in greeting["response"].lower()

        menu = asyncio.run(workflow.run("Show me the menu", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-2"))
        assert "menu" in menu["response"].lower()

        add_valid = asyncio.run(workflow.run("Add 2 burgers", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-3"))
        assert add_valid["cart"][0]["product_id"] == burger.id
        assert add_valid["cart"][0]["quantity"] == 2

        invalid_product = asyncio.run(workflow.run("Add 1 taco", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-4"))
        assert "couldn't find" in invalid_product["response"].lower()

        unavailable_product = asyncio.run(workflow.run("Add 1 soup", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-5"))
        assert "couldn't find" in unavailable_product["response"].lower() or "not available" in unavailable_product["response"].lower()

        zero_quantity = asyncio.run(workflow.run("Add 0 fries", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-6"))
        assert "greater than zero" in zero_quantity["response"].lower()

        negative_quantity = asyncio.run(workflow.run("Add -2 fries", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-7"))
        assert "greater than zero" in negative_quantity["response"].lower()

        add_fries = asyncio.run(workflow.run("Add 3 fries", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-8"))
        assert any(item["product_id"] == fries.id and item["quantity"] == 3 for item in add_fries["cart"])

        cart = asyncio.run(workflow.run("View my cart", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-9"))
        assert "36.50" in cart["response"]

        remove_item = asyncio.run(workflow.run("Remove fries from my cart", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-10"))
        assert "removed fries" in remove_item["response"].lower()

        cart_after_remove = asyncio.run(workflow.run("View my cart", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-11"))
        assert "20.00" in cart_after_remove["response"]

        policy = asyncio.run(workflow.run("What is your delivery policy?", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-12"))
        assert "policy response" in policy["response"]
        assert len(policy["cart"]) == 1

        address = asyncio.run(workflow.run("I live at 123 Main St", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-13"))
        assert address["address"] == "I live at 123 Main St"

        confirm = asyncio.run(workflow.run("Confirm my order", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-14"))
        assert confirm["order_number"].startswith("ORD-")
        assert confirm["order_status"] == "confirmed"
        assert "20.00" in confirm["response"]

        duplicate_message = asyncio.run(workflow.run("Confirm my order", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-14"))
        assert duplicate_message["order_number"] == confirm["order_number"]
        assert duplicate_message["order_status"] == "confirmed"

        explicit_status = asyncio.run(workflow.run(f"What is the status of order {confirm['order_number']}?", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-15"))
        assert explicit_status["order_status"] == "confirmed"
        assert confirm["order_number"] in explicit_status["response"]

        remembered_status = asyncio.run(workflow.run("What is my order status?", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-16"))
        assert remembered_status["order_status"] == "confirmed"

        empty_conversation = "conv-empty"
        empty_confirm = asyncio.run(workflow.run("Confirm my order", conversation_id=empty_conversation, customer_phone="15551234567", message_id="m-17"))
        assert "cart is empty" in empty_confirm["response"].lower()

        fallback = asyncio.run(workflow.run("Tell me something unrelated", conversation_id=conversation_id, customer_phone="15551234567", message_id="m-18"))
        assert "policy response" not in fallback["response"].lower()
        assert fallback["cart"] == remembered_status["cart"]

        state = workflow.memory.get(conversation_id)
        assert state["customer_phone"] == "15551234567"
        assert len(state["messages"]) >= 2

        direct_phone = asyncio.run(workflow.run("Hello", conversation_id="conv-direct", customer_phone="test:+15550000000", message_id="m-19"))
        assert "hello" in direct_phone["response"].lower()
    finally:
        cleanup()
