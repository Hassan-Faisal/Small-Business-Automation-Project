from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate
from app.services.order_service import OrderService
from app.services.product_service import ProductService


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_product_service_crud_and_normalized_lookup(db_session):
    service = ProductService(db_session)

    created = service.create_product(
        name="  Chicken Burger  ",
        description="Grilled",
        price=Decimal("12.50"),
        is_available=True,
    )

    assert created.id is not None
    assert service.list_available_products()[0].name == "Chicken Burger"
    assert service.retrieve_product_by_id(created.id).id == created.id
    assert service.retrieve_product_by_normalized_name("chicken   burger").id == created.id

    updated = service.update_product_availability(created.id, False)
    assert updated.is_available is False
    assert service.list_available_products() == []


def test_order_service_creates_draft_and_confirms(db_session):
    product_service = ProductService(db_session)
    burger = product_service.create_product(
        name="Burger",
        description="Classic",
        price=Decimal("10.00"),
        is_available=True,
    )
    fries = product_service.create_product(
        name="Fries",
        description="Side",
        price=Decimal("5.50"),
        is_available=True,
    )

    order_service = OrderService(db_session)
    draft = order_service.create_draft_order(
        OrderCreate(
            order_number="ORD-1001",
            customer_phone="+123456789",
            delivery_address="123 Main St",
            items=[
                {"product_id": burger.id, "quantity": 2},
                {"product_id": fries.id, "quantity": 1},
            ],
        )
    )

    assert draft.status == "draft"
    assert draft.total_amount == Decimal("25.50")
    assert len(draft.items) == 2
    assert draft.items[0].unit_price in {Decimal("10.00"), Decimal("5.50")}
    assert draft.items[0].subtotal in {Decimal("20.00"), Decimal("5.50")}

    loaded = order_service.retrieve_order_by_order_number("ORD-1001")
    assert loaded is not None
    assert loaded.total_amount == Decimal("25.50")

    confirmed = order_service.confirm_order("ORD-1001")
    assert confirmed.status == "confirmed"

    with pytest.raises(ValueError, match="already confirmed"):
        order_service.confirm_order("ORD-1001")


def test_order_service_rejects_empty_order_and_invalid_products(db_session):
    service = OrderService(db_session)

    with pytest.raises(Exception):
        service.create_draft_order(
            OrderCreate(
                order_number="ORD-EMPTY",
                customer_phone="+123456789",
                delivery_address="123 Main St",
                items=[],
            )
        )

    product_service = ProductService(db_session)
    unavailable = product_service.create_product(
        name="Soup",
        description="Hot",
        price=Decimal("4.00"),
        is_available=False,
    )

    with pytest.raises(ValueError, match="not available"):
        service.create_draft_order(
            OrderCreate(
                order_number="ORD-2001",
                customer_phone="+123456789",
                delivery_address="123 Main St",
                items=[{"product_id": unavailable.id, "quantity": 1}],
            )
        )

    empty_order = Order(
        order_number="ORD-ZERO",
        customer_phone="+123456789",
        delivery_address="123 Main St",
        status="draft",
        total_amount=Decimal("0.00"),
    )
    db_session.add(empty_order)
    db_session.commit()

    with pytest.raises(ValueError, match="empty order"):
        service.confirm_order("ORD-ZERO")


def test_business_services_validate_input_and_rollback_on_failure(db_session):
    product_service = ProductService(db_session)

    with pytest.raises(ValueError, match="name"):
        product_service.create_product(
            name="   ",
            description="blank",
            price=Decimal("2.00"),
            is_available=True,
        )

    product = product_service.create_product(
        name="Salad",
        description="Fresh",
        price=Decimal("8.00"),
        is_available=True,
    )

    order_service = OrderService(db_session)

    with pytest.raises(ValueError, match="greater than zero"):
        order_service.create_draft_order(
            OrderCreate(
                order_number="ORD-3001",
                customer_phone="+15551234567",
                delivery_address="456 Oak St",
                items=[{"product_id": product.id, "quantity": 0}],
            )
        )

    assert db_session.query(Order).count() == 0
    assert db_session.query(OrderItem).count() == 0
