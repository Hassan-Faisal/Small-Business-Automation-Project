from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate
from app.services.order_service import OrderService
from app.services.product_service import ProductService


def test_order_service_creates_draft_confirms_and_tracks(db_session):
    product_service = ProductService(db_session)
    burger = product_service.create_product(name='Burger', description='Classic', price=Decimal('10.00'), is_available=True)
    fries = product_service.create_product(name='Fries', description='Side', price=Decimal('5.50'), is_available=True)

    order_service = OrderService(db_session)
    draft = order_service.create_draft_order(
        OrderCreate(
            order_number='ORD-1001',
            customer_phone='15551234567',
            delivery_address='123 Main St',
            items=[
                {'product_id': burger.id, 'quantity': 2},
                {'product_id': fries.id, 'quantity': 1},
            ],
        )
    )

    assert draft.status == 'draft'
    assert draft.total_amount == Decimal('25.50')
    assert len(draft.items) == 2

    loaded = order_service.retrieve_order_by_order_number('ORD-1001')
    assert loaded is not None
    assert loaded.total_amount == Decimal('25.50')

    confirmed = order_service.confirm_order('ORD-1001')
    assert confirmed.status == 'confirmed'

    with pytest.raises(ValueError, match='already confirmed'):
        order_service.confirm_order('ORD-1001')

    updated = order_service.update_order_status('ORD-1001', 'delivered')
    assert updated.status == 'delivered'


def test_order_service_rejects_invalid_input(db_session):
    order_service = OrderService(db_session)
    product_service = ProductService(db_session)

    salad = product_service.create_product(name='Salad', description='Fresh', price=Decimal('8.00'), is_available=True)
    soup = product_service.create_product(name='Soup', description='Hot', price=Decimal('4.00'), is_available=False)

    with pytest.raises(ValidationError, match='too_short'):
        OrderCreate(
            order_number='ORD-EMPTY',
            customer_phone='15551234567',
            delivery_address='123 Main St',
            items=[],
        )

    with pytest.raises(ValueError, match='greater than zero'):
        order_service.create_draft_order(
            OrderCreate(
                order_number='ORD-ZERO',
                customer_phone='15551234567',
                delivery_address='123 Main St',
                items=[{'product_id': salad.id, 'quantity': 0}],
            )
        )

    with pytest.raises(ValueError, match='not available'):
        order_service.create_draft_order(
            OrderCreate(
                order_number='ORD-UNAVAILABLE',
                customer_phone='15551234567',
                delivery_address='123 Main St',
                items=[{'product_id': soup.id, 'quantity': 1}],
            )
        )

    empty_order = Order(
        order_number='ORD-ZERO2',
        customer_phone='15551234567',
        delivery_address='123 Main St',
        status='draft',
        total_amount=Decimal('0.00'),
    )
    db_session.add(empty_order)
    db_session.commit()

    with pytest.raises(ValueError, match='empty order'):
        order_service.confirm_order('ORD-ZERO2')
