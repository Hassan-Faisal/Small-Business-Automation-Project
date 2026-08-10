from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import auth_router, router as admin_router
from app.api.routes.admin_dashboard import get_admin_dashboard_service, router as dashboard_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.conversation_state import ConversationStateRecord
from app.models.customer_subscription import CustomerSubscription
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.subscription_plan import SubscriptionPlan
from app.services.admin_dashboard_service import AdminDashboardService
from app.schemas.admin_dashboard import DashboardPeriod

FIXED_NOW = datetime(2026, 8, 2, 0, 30, tzinfo=timezone.utc)


def build_dashboard_app(db_session, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "ADMIN_AUTH_SECRET", "test-admin-secret-that-is-long-enough")
    monkeypatch.setattr(settings, "ADMIN_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "BUSINESS_TIMEZONE", "Asia/Karachi")
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(dashboard_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_admin_dashboard_service] = lambda: AdminDashboardService(db_session, clock=lambda: FIXED_NOW)
    return app


def create_admin(db_session) -> AdminUser:
    admin = AdminUser(
        full_name="Business Owner",
        email="owner@example.com",
        hashed_password=hash_password("StrongPassword1"),
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def add_product(db_session, name: str) -> Product:
    product = Product(name=name, price=Decimal("100.00"), is_available=True)
    db_session.add(product)
    db_session.flush()
    return product


def add_order(
    db_session,
    *,
    order_number: str,
    customer_phone: str,
    status: str,
    created_at: datetime,
    total_amount: Decimal,
    items: list[tuple[Product, int]] = (),
) -> Order:
    order = Order(
        order_number=order_number,
        customer_phone=customer_phone,
        delivery_address="House 1, Main Street",
        status=status,
        total_amount=total_amount,
        created_at=created_at,
    )
    db_session.add(order)
    db_session.flush()
    for product, quantity in items:
        db_session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
                subtotal=product.price * quantity,
            )
        )
    return order


def login(client: TestClient) -> None:
    response = client.post("/admin/auth/login", json={"email": "owner@example.com", "password": "StrongPassword1"})
    assert response.status_code == 200


def test_dashboard_requires_authenticated_admin(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    app = build_dashboard_app(db_session, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/admin/dashboard/summary")

    assert response.status_code == 401


def test_empty_dashboard_returns_zero_and_null_values(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    app = build_dashboard_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.get("/admin/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["today_orders"] == 0
    assert body["today_revenue"] in {"0.00", 0, 0.0}
    assert body["active_subscriptions"] == 0
    assert body["total_customers"] == 0
    assert body["top_selling_item"] is None
    assert body["recent_orders"] == []


def test_dashboard_counts_statuses_revenue_top_item_customers_and_recent_orders(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    chicken = add_product(db_session, "Chicken Biryani")
    pizza = add_product(db_session, "Pizza")
    inside = FIXED_NOW - timedelta(hours=1)
    boundary_inside = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)
    outside = datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc)

    add_order(db_session, order_number="ORD-OLD", customer_phone="old", status="delivered", created_at=outside, total_amount=Decimal("999.00"), items=[(pizza, 9)])
    add_order(db_session, order_number="ORD-DRAFT", customer_phone="111", status="draft", created_at=inside, total_amount=Decimal("10.00"))
    add_order(db_session, order_number="ORD-CONF", customer_phone="222", status="confirmed", created_at=inside + timedelta(minutes=1), total_amount=Decimal("20.00"), items=[(chicken, 2)])
    add_order(db_session, order_number="ORD-COMP", customer_phone="333", status="completed", created_at=inside + timedelta(minutes=2), total_amount=Decimal("30.00"), items=[(chicken, 3)])
    add_order(db_session, order_number="ORD-DELIV", customer_phone="444", status="delivered", created_at=boundary_inside, total_amount=Decimal("40.00"), items=[(pizza, 4)])
    add_order(db_session, order_number="ORD-CANCEL", customer_phone="555", status="cancelled", created_at=inside + timedelta(minutes=3), total_amount=Decimal("500.00"), items=[(chicken, 50)])
    add_order(db_session, order_number="ORD-UNKNOWN", customer_phone="666", status="mystery_status", created_at=inside + timedelta(minutes=4), total_amount=Decimal("60.00"))
    for index in range(6):
        add_order(db_session, order_number=f"ORD-RECENT-{index}", customer_phone=f"recent-{index}", status="confirmed", created_at=inside + timedelta(minutes=10 + index), total_amount=Decimal("1.00"))

    plan = SubscriptionPlan(name="Dashboard Plan", duration_type="weekly", number_of_days=7, included_meal_types=["lunch"], price=Decimal("100.00"))
    db_session.add(plan)
    db_session.flush()
    db_session.add_all(
        [
            CustomerSubscription(customer_phone="subscriber", subscription_plan_id=plan.id, start_date=date(2026, 8, 1), end_date=date(2026, 8, 5), status="active", preferred_meal_choices=[]),
            CustomerSubscription(customer_phone="expired", subscription_plan_id=plan.id, start_date=date(2026, 7, 1), end_date=date(2026, 7, 31), status="active", preferred_meal_choices=[]),
        ]
    )
    db_session.add(ConversationStateRecord(conversation_id="conversation-only", customer_phone="conversation-customer", cart=[], messages=[], processed_message_ids=[]))
    db_session.commit()

    app = build_dashboard_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        response = client.get("/admin/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["today_orders"] == 12
    assert body["draft_orders"] == 1
    assert body["pending_orders"] == 1
    assert body["confirmed_orders"] == 7
    assert body["completed_orders"] == 1
    assert body["delivered_orders"] == 2
    assert body["cancelled_orders"] == 1
    assert body["today_revenue"] == "70.00"
    assert body["active_subscriptions"] == 1
    assert body["total_customers"] == 16
    assert body["top_selling_item"] == {"name": "Chicken Biryani", "quantity": 5, "revenue": "500.00"}
    assert body["total_orders"] == 10
    assert body["total_revenue"] == "1069.00"
    assert body["period_orders"] == 9
    assert body["period_revenue"] == "70.00"
    assert len(body["performance"]) == 1
    assert len(body["recent_orders"]) == 5
    assert body["recent_orders"][0]["order_number"] == "ORD-RECENT-5"
    assert body["recent_orders"][-1]["order_number"] == "ORD-RECENT-1"


def test_business_timezone_boundary_includes_local_today(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    product = add_product(db_session, "Boundary Meal")
    boundary_order = add_order(
        db_session,
        order_number="ORD-BOUNDARY",
        customer_phone="boundary",
        status="completed",
        created_at=datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc),
        total_amount=Decimal("12.34"),
        items=[(product, 1)],
    )
    old_order = add_order(
        db_session,
        order_number="ORD-OUTSIDE",
        customer_phone="outside",
        status="completed",
        created_at=datetime(2026, 8, 1, 18, 59, tzinfo=timezone.utc),
        total_amount=Decimal("99.99"),
    )
    db_session.commit()

    monkeypatch.setattr(settings, "BUSINESS_TIMEZONE", "Asia/Karachi")
    summary = AdminDashboardService(db_session, clock=lambda: FIXED_NOW).get_summary()

    assert summary.today_orders == 1
    assert summary.today_revenue == Decimal("12.34")
    assert summary.recent_orders[0].id == boundary_order.id


def test_dashboard_periods_and_operational_counts_use_correct_scopes(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    product = add_product(db_session, "Period Meal")
    old = FIXED_NOW - timedelta(days=8)
    older_active = FIXED_NOW - timedelta(days=2)
    add_order(db_session, order_number="ORD-OLD-FULFILLED", customer_phone="old", status="completed", created_at=old, total_amount=Decimal("100.00"), items=[(product, 1)])
    add_order(db_session, order_number="ORD-OLD-PREPARING", customer_phone="prep", status="preparing", created_at=older_active, total_amount=Decimal("20.00"), items=[(product, 1)])
    add_order(db_session, order_number="ORD-OLD-CANCELLED", customer_phone="cancel", status="cancelled", created_at=older_active, total_amount=Decimal("500.00"), items=[(product, 10)])
    db_session.commit()

    app = build_dashboard_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        seven = client.get("/admin/dashboard/summary", params={"period": "7d"}).json()
        thirty = client.get("/admin/dashboard/summary", params={"period": "30d"}).json()
        all_time = client.get("/admin/dashboard/summary", params={"period": "all"}).json()
        invalid = client.get("/admin/dashboard/summary", params={"period": "90d"})

    assert seven["period"] == "7d"
    assert seven["period_orders"] == 1
    assert seven["period_revenue"] == "0.00"
    assert thirty["period_orders"] == 2
    assert thirty["period_revenue"] == "100.00"
    assert all_time["total_orders"] == 2
    assert all_time["total_revenue"] == "100.00"
    assert all_time["preparing_orders"] == 1
    assert all_time["top_selling_item"] == {"name": "Period Meal", "quantity": 2, "revenue": "200.00"}
    assert len(seven["performance"]) == 7
    assert len(thirty["performance"]) == 30
    assert len(all_time["performance"]) == 2
    assert invalid.status_code == 422


def test_dashboard_empty_performance_has_seven_zero_days(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    app = build_dashboard_app(db_session, monkeypatch)
    with TestClient(app) as client:
        login(client)
        response = client.get("/admin/dashboard/summary", params={"period": "all"})
    body = response.json()
    assert response.status_code == 200
    assert body["period_orders"] == 0
    assert body["total_revenue"] in {"0.00", 0, 0.0}
    assert len(body["performance"]) == 1
    assert all(point["orders"] == 0 for point in body["performance"])


def test_confirmed_orders_count_today_but_do_not_count_as_revenue(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    product = add_product(db_session, "Confirmed Meal")
    add_order(db_session, order_number="ORD-CONF-TODAY", customer_phone="confirmed-today", status="confirmed", created_at=datetime(2026, 8, 1, 23, 59, tzinfo=timezone.utc), total_amount=Decimal("760.00"), items=[(product, 2)])
    add_order(db_session, order_number="ORD-DONE-TODAY", customer_phone="done-today", status="completed", created_at=datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc), total_amount=Decimal("320.00"), items=[(product, 1)])
    db_session.commit()

    monkeypatch.setattr(settings, "BUSINESS_TIMEZONE", "Asia/Karachi")
    summary = AdminDashboardService(db_session, clock=lambda: FIXED_NOW).get_summary()

    assert summary.today_orders == 2
    assert summary.confirmed_orders == 1
    assert summary.today_revenue == Decimal("320.00")
    assert summary.total_revenue == Decimal("320.00")


def test_business_day_boundaries_use_asia_karachi_date(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    product = add_product(db_session, "Boundary Case Meal")
    timestamps = [
        ("ORD-UTC-1859", datetime(2026, 8, 1, 18, 59, tzinfo=timezone.utc), "completed"),
        ("ORD-UTC-1900", datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc), "confirmed"),
        ("ORD-UTC-2359", datetime(2026, 8, 1, 23, 59, tzinfo=timezone.utc), "completed"),
        ("ORD-UTC-0000", datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc), "confirmed"),
        ("ORD-UTC-1900-NEXT", datetime(2026, 8, 2, 19, 0, tzinfo=timezone.utc), "completed"),
    ]
    for order_number, created_at, status in timestamps:
        add_order(db_session, order_number=order_number, customer_phone=order_number, status=status, created_at=created_at, total_amount=Decimal("10.00"), items=[(product, 1)])
    db_session.commit()

    monkeypatch.setattr(settings, "BUSINESS_TIMEZONE", "Asia/Karachi")
    summary = AdminDashboardService(db_session, clock=lambda: FIXED_NOW).get_summary()

    assert summary.today_orders == 3
    assert summary.confirmed_orders == 2
    assert summary.today_revenue == Decimal("10.00")


def test_dashboard_contract_includes_all_metric_groups_and_decimal_serialization(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    previous = datetime(2026, 8, 1, 18, 0, tzinfo=timezone.utc)
    today_confirmed = datetime(2026, 8, 1, 20, 0, tzinfo=timezone.utc)
    today_cancelled = datetime(2026, 8, 1, 21, 0, tzinfo=timezone.utc)
    today_completed = datetime(2026, 8, 1, 22, 0, tzinfo=timezone.utc)
    add_order(db_session, order_number="ORD-PREVIOUS", customer_phone="previous", status="confirmed", created_at=previous, total_amount=Decimal("185.00"))
    add_order(db_session, order_number="ORD-TODAY-CONF", customer_phone="today-confirmed", status="confirmed", created_at=today_confirmed, total_amount=Decimal("760.00"))
    add_order(db_session, order_number="ORD-TODAY-CANCEL", customer_phone="today-cancelled", status="cancelled", created_at=today_cancelled, total_amount=Decimal("500.00"))
    add_order(db_session, order_number="ORD-TODAY-DONE", customer_phone="today-done", status="completed", created_at=today_completed, total_amount=Decimal("320.00"))
    db_session.commit()

    summary = AdminDashboardService(db_session, clock=lambda: FIXED_NOW).get_summary(DashboardPeriod.TODAY)
    body = summary.model_dump(mode="json")

    assert body["period"] == "today"
    assert body["total_orders"] == 3
    assert body["total_revenue"] == "320.00"
    assert body["period_orders"] == 2
    assert body["period_revenue"] == "320.00"
    assert body["today_orders"] == 3
    assert body["today_revenue"] == "320.00"
    assert body["confirmed_orders"] == 2
    assert body["cancelled_orders"] == 1
    assert body["completed_orders"] == 1
    assert body["recent_orders"][0]["order_number"] == "ORD-TODAY-DONE"
