from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.product_service import ProductService


def test_product_service_crud_and_lookup(db_session):
    service = ProductService(db_session)

    created = service.create_product(
        name='  Chicken Burger  ',
        description='Grilled',
        price=Decimal('12.50'),
        is_available=True,
    )

    assert created.id is not None
    assert service.list_available_products()[0].name == 'Chicken Burger'
    assert service.retrieve_product_by_id(created.id).id == created.id
    assert service.retrieve_product_by_normalized_name('chicken   burger').id == created.id

    updated = service.update_product_availability(created.id, False)
    assert updated.is_available is False
    assert service.list_available_products() == []


def test_product_service_rejects_blank_name(db_session):
    service = ProductService(db_session)

    with pytest.raises(ValueError, match='Product name is required'):
        service.create_product(
            name='   ',
            description='blank',
            price=Decimal('2.00'),
            is_available=True,
        )
