from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.admin import auth_router, router as admin_router
from app.api.routes.admin_orders import get_admin_order_service, router as admin_orders_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.admin_order_service import AdminOrderService


def build_app(db_session, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "ADMIN_AUTH_SECRET", "test-admin-secret-that-is-long-enough")
    monkeypatch.setattr(settings, "ADMIN_COOKIE_SECURE", False)
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(admin_orders_router)
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_admin_order_service] = lambda: AdminOrderService(db_session)
    return app


def create_admin(db_session, email: str = "owner@example.com") -> AdminUser:
    admin = AdminUser(full_name="Owner", email=email, hashed_password=hash_password("StrongPassword1"))
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def add_order(db_session, number: str, status: str, created_at: datetime, phone: str = "03001234567") -> Order:
    product = db_session.query(Product).filter_by(name="Meal").first()
    if product is None:
        product = Product(name="Meal", price=Decimal("125.50"), is_available=True)
        db_session.add(product)
        db_session.flush()
    order = Order(order_number=number, customer_phone=phone, delivery_address="House 1", status=status, total_amount=Decimal("251.00"), created_at=created_at)
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=2, unit_price=Decimal("125.50"), subtotal=Decimal("251.00")))
    db_session.commit()
    return order


def login(client: TestClient) -> None:
    assert client.post("/admin/auth/login", json={"email": "owner@example.com", "password": "StrongPassword1"}).status_code == 200


def test_admin_orders_require_auth_and_empty_response(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    app = build_app(db_session, monkeypatch)
    with TestClient(app) as client:
        assert client.get("/admin/orders").status_code == 401
        login(client)
        response = client.get("/admin/orders")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_list_filters_pagination_newest_first_and_decimal_safe(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    now = datetime.now(timezone.utc)
    add_order(db_session, "ORD-OLD", "confirmed", now - timedelta(days=2), "03001111111")
    newest = add_order(db_session, "ORD-NEW", "preparing", now, "03002222222")
    add_order(db_session, "ORD-OTHER", "cancelled", now - timedelta(days=1), "03003333333")
    app = build_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        response = client.get("/admin/orders", params={"status": "preparing", "page_size": 1})
        phone_response = client.get("/admin/orders", params={"customer_phone": "2222"})
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == newest.id
    assert response.json()["items"][0]["total_amount"] == "251.00"
    assert response.json()["items"][0]["item_count"] == 1
    assert phone_response.json()["total"] == 1


def test_detail_items_status_lifecycle_timestamps_and_delivery(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    order = add_order(db_session, "ORD-LIFE", "draft", datetime.now(timezone.utc))
    original_price = db_session.query(OrderItem).filter_by(order_id=order.id).one().unit_price
    app = build_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        detail = client.get(f"/admin/orders/{order.id}")
        confirmed = client.patch(f"/admin/orders/{order.id}/status", json={"status": "confirmed"})
        preparing = client.patch(f"/admin/orders/{order.id}/status", json={"status": "preparing"})
        delivery = client.patch(f"/admin/orders/{order.id}/delivery", json={"estimated_delivery_minutes": 40, "delivery_provider": "BYKEA", "rider_note": "Call on arrival", "internal_note": "Priority"})
    assert detail.status_code == 200
    assert detail.json()["items"][0]["product_name"] == "Meal"
    assert detail.json()["items"][0]["unit_price"] == "125.50"
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_at"] is not None
    assert preparing.status_code == 200
    assert delivery.status_code == 200
    assert delivery.json()["delivery_provider"] == "bykea"
    assert db_session.query(OrderItem).filter_by(order_id=order.id).one().unit_price == original_price


def test_invalid_and_terminal_transitions_and_missing_order(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    order = add_order(db_session, "ORD-INVALID", "confirmed", datetime.now(timezone.utc))
    completed = add_order(db_session, "ORD-DONE", "completed", datetime.now(timezone.utc))
    app = build_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        assert client.get("/admin/orders/999999").status_code == 404
        assert client.patch(f"/admin/orders/{order.id}/status", json={"status": "draft"}).status_code == 409
        assert client.patch(f"/admin/orders/{completed.id}/status", json={"status": "confirmed"}).status_code == 409
        assert client.patch(f"/admin/orders/{order.id}/delivery", json={"delivery_provider": "fast-rider"}).status_code == 422


def test_status_transaction_rolls_back_without_partial_write(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    order = add_order(db_session, "ORD-ROLLBACK", "draft", datetime.now(timezone.utc))
    admin = create_admin(db_session, email="second@example.com")
    service = AdminOrderService(db_session)
    original_commit = db_session.commit

    def fail_commit() -> None:
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        service.update_status(order.id, "confirmed", admin)
    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.expire_all()
    persisted = db_session.get(Order, order.id)
    assert persisted is not None
    assert persisted.status == "draft"
    assert persisted.confirmed_at is None





