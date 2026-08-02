from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.admin import auth_router, router as admin_router
from app.api.routes.admin_menu import router as admin_menu_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.meal_offering import MealOffering
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.admin_menu_service import AdminMenuService, MenuItemPersistenceError

PASSWORD = "StrongPassword1"


def build_admin_menu_app(db_session, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "ADMIN_AUTH_SECRET", "test-admin-secret-that-is-long-enough")
    monkeypatch.setattr(settings, "ADMIN_COOKIE_SECURE", False)
    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(admin_menu_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


def create_admin(db_session) -> AdminUser:
    admin = AdminUser(
        full_name="Business Owner",
        email="owner@example.com",
        hashed_password=hash_password(PASSWORD),
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def login(client: TestClient) -> None:
    response = client.post("/admin/auth/login", json={"email": "owner@example.com", "password": PASSWORD})
    assert response.status_code == 200


def menu_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Test Chicken Meal",
        "description": "A test meal.",
        "price": "275.50",
        "meal_type": "lunch",
        "day_of_week": "Monday",
        "availability": True,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def create_menu(service: AdminMenuService, **overrides: object) -> MealOffering:
    payload = menu_payload(**overrides)
    return service.create_menu_item(
        name=str(payload["name"]),
        description=payload["description"] if isinstance(payload["description"], str) else None,
        price=Decimal(str(payload["price"])),
        meal_type=str(payload["meal_type"]),
        day_of_week=str(payload["day_of_week"]),
        availability=bool(payload["availability"]),
        is_active=bool(payload["is_active"]),
    )


def product_by_name(db_session, name: str) -> Product | None:
    return db_session.scalars(
        select(Product).where(func.lower(func.trim(Product.name)) == name.strip().lower())
    ).first()


def test_all_menu_routes_require_authentication(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    app = build_admin_menu_app(db_session, monkeypatch)
    requests = [
        ("get", "/admin/menu-items", None),
        ("post", "/admin/menu-items", menu_payload()),
        ("get", "/admin/menu-items/999", None),
        ("patch", "/admin/menu-items/999", {"price": "300.00"}),
        ("patch", "/admin/menu-items/999/availability", {"availability": False}),
        ("delete", "/admin/menu-items/999", None),
    ]

    with TestClient(app) as client:
        for method, path, body in requests:
            response = client.request(method, path, json=body)
            assert response.status_code == 401


def test_authenticated_owner_can_list_paginated_items_with_stable_serialization(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Serialization Meal")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.get("/admin/menu-items", params={"page": 1, "page_size": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["items"] == [
        {
            "id": item.id,
            "name": "Serialization Meal",
            "description": "A test meal.",
            "price": "275.50",
            "meal_type": "lunch",
            "day_of_week": "Monday",
            "availability": True,
            "is_active": True,
        }
    ]


def test_list_filters_normalize_values_and_filter_flags(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    service = AdminMenuService(db_session)
    create_menu(service, name="Monday Lunch", day_of_week="Monday", meal_type="lunch")
    create_menu(service, name="Tuesday Lunch", day_of_week="Tuesday", meal_type="lunch", availability=False)
    create_menu(service, name="Monday Dinner", day_of_week="Monday", meal_type="dinner", is_active=False)
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.get(
            "/admin/menu-items",
            params={"meal_type": " LUNCH ", "day_of_week": "monday", "availability": True, "is_active": True},
        )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Monday Lunch"]


def test_list_searches_name_and_description(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    service = AdminMenuService(db_session)
    create_menu(service, name="Spicy Kofta", description="Beef curry")
    create_menu(service, name="Plain Rice", description="Aromatic basmati", day_of_week="Tuesday")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        by_name = client.get("/admin/menu-items", params={"search": "kofta"})
        by_description = client.get("/admin/menu-items", params={"search": "basmati"})

    assert [item["name"] for item in by_name.json()["items"]] == ["Spicy Kofta"]
    assert [item["name"] for item in by_description.json()["items"]] == ["Plain Rice"]


def test_valid_creation_normalizes_values_and_creates_orderable_product(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/admin/menu-items",
            json=menu_payload(name="  New   Chicken Box ", meal_type="DINNER", day_of_week="sunday"),
        )

    assert response.status_code == 201
    assert response.json()["name"] == "New Chicken Box"
    assert response.json()["meal_type"] == "dinner"
    assert response.json()["day_of_week"] == "Sunday"
    product = product_by_name(db_session, "New Chicken Box")
    assert product is not None
    assert product.price == Decimal("275.50")
    assert product.is_available is True


@pytest.mark.parametrize(
    ("field", "value"),
    [("meal_type", "brunch"), ("day_of_week", "Funday"), ("price", "0.00"), ("price", "-1.00")],
)
def test_invalid_create_values_are_rejected(db_session, monkeypatch: pytest.MonkeyPatch, field: str, value: str) -> None:
    create_admin(db_session)
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.post("/admin/menu-items", json=menu_payload(**{field: value}))

    assert response.status_code == 422
    assert db_session.scalar(select(func.count(MealOffering.id))) == 0


def test_duplicate_creation_is_rejected_case_insensitively(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    create_menu(AdminMenuService(db_session), name="Duplicate Meal")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.post("/admin/menu-items", json=menu_payload(name=" duplicate meal "))

    assert response.status_code == 409
    assert db_session.scalar(select(func.count(MealOffering.id))) == 1


def test_single_item_retrieval_and_missing_item(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Retrieval Meal")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        found = client.get(f"/admin/menu-items/{item.id}")
        missing = client.get("/admin/menu-items/999999")

    assert found.status_code == 200
    assert found.json()["name"] == "Retrieval Meal"
    assert missing.status_code == 404
    assert "not found" in missing.json()["detail"].lower()


def test_partial_update_changes_only_requested_fields(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Partial Meal")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.patch(
            f"/admin/menu-items/{item.id}",
            json={"description": "Updated description", "day_of_week": "wednesday"},
        )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"
    assert response.json()["day_of_week"] == "Wednesday"
    assert response.json()["price"] == "275.50"
    assert response.json()["meal_type"] == "lunch"


def test_price_update_synchronizes_product_and_same_name_schedule_entries(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    service = AdminMenuService(db_session)
    first = create_menu(service, name="Shared Meal", day_of_week="Monday")
    second = create_menu(service, name="Shared Meal", day_of_week="Tuesday")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.patch(f"/admin/menu-items/{first.id}", json={"price": "325.00"})

    assert response.status_code == 200
    db_session.refresh(second)
    product = product_by_name(db_session, "Shared Meal")
    assert response.json()["price"] == "325.00"
    assert second.price == Decimal("325.00")
    assert product is not None and product.price == Decimal("325.00")


def test_name_update_keeps_product_alignment_without_history(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Old Menu Name")
    original_product = product_by_name(db_session, "Old Menu Name")
    assert original_product is not None
    original_product_id = original_product.id
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.patch(f"/admin/menu-items/{item.id}", json={"name": "New Menu Name"})

    assert response.status_code == 200
    renamed_product = product_by_name(db_session, "New Menu Name")
    assert renamed_product is not None
    assert renamed_product.id == original_product_id
    assert product_by_name(db_session, "Old Menu Name") is None


def test_conflicting_update_is_rejected(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    service = AdminMenuService(db_session)
    first = create_menu(service, name="First Meal")
    create_menu(service, name="Second Meal")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.patch(f"/admin/menu-items/{first.id}", json={"name": "Second Meal"})

    assert response.status_code == 409
    db_session.refresh(first)
    assert first.name == "First Meal"


def test_availability_toggle_recalculates_shared_product(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    service = AdminMenuService(db_session)
    first = create_menu(service, name="Availability Meal", day_of_week="Monday")
    second = create_menu(service, name="Availability Meal", day_of_week="Tuesday")
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        first_response = client.patch(f"/admin/menu-items/{first.id}/availability", json={"availability": False})
        assert first_response.status_code == 200
        assert product_by_name(db_session, "Availability Meal").is_available is True  # type: ignore[union-attr]
        second_response = client.patch(f"/admin/menu-items/{second.id}/availability", json={"availability": False})

    assert second_response.status_code == 200
    assert product_by_name(db_session, "Availability Meal").is_available is False  # type: ignore[union-attr]


def test_delete_soft_deactivates_and_preserves_rows(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Deactivate Meal")
    product = product_by_name(db_session, "Deactivate Meal")
    assert product is not None
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        response = client.delete(f"/admin/menu-items/{item.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Menu item deactivated successfully."
    persisted = db_session.get(MealOffering, item.id)
    assert persisted is not None
    assert persisted.is_active is False
    assert persisted.availability is False
    db_session.refresh(product)
    assert product.is_available is False


def test_updates_do_not_modify_historical_order_items_or_old_product_identity(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    create_admin(db_session)
    item = create_menu(AdminMenuService(db_session), name="Historical Meal", price="250.00")
    old_product = product_by_name(db_session, "Historical Meal")
    assert old_product is not None
    order = Order(
        order_number="ORD-HISTORY",
        customer_phone="15551234567",
        delivery_address="House 1",
        status="confirmed",
        total_amount=Decimal("500.00"),
    )
    db_session.add(order)
    db_session.flush()
    order_item = OrderItem(
        order_id=order.id,
        product_id=old_product.id,
        quantity=2,
        unit_price=Decimal("250.00"),
        subtotal=Decimal("500.00"),
    )
    db_session.add(order_item)
    db_session.commit()
    old_product_id = old_product.id
    order_item_id = order_item.id
    app = build_admin_menu_app(db_session, monkeypatch)

    with TestClient(app) as client:
        login(client)
        price_response = client.patch(f"/admin/menu-items/{item.id}", json={"price": "300.00"})
        rename_response = client.patch(f"/admin/menu-items/{item.id}", json={"name": "Current Meal"})

    assert price_response.status_code == 200
    assert rename_response.status_code == 200
    db_session.expire_all()
    historical_item = db_session.get(OrderItem, order_item_id)
    historical_product = db_session.get(Product, old_product_id)
    current_product = product_by_name(db_session, "Current Meal")
    assert historical_item is not None
    assert historical_item.product_id == old_product_id
    assert historical_item.unit_price == Decimal("250.00")
    assert historical_item.subtotal == Decimal("500.00")
    assert historical_product is not None and historical_product.name == "Historical Meal"
    assert historical_product.is_available is False
    assert current_product is not None and current_product.id != old_product_id
    assert current_product.price == Decimal("300.00")


def test_transaction_rollback_prevents_partial_product_and_offering_writes(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AdminMenuService(db_session)
    original_commit = db_session.commit

    def fail_commit() -> None:
        raise SQLAlchemyError("forced commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(MenuItemPersistenceError, match="Unable to save"):
        create_menu(service, name="Rollback Meal")
    monkeypatch.setattr(db_session, "commit", original_commit)

    assert product_by_name(db_session, "Rollback Meal") is None
    assert db_session.scalars(select(MealOffering).where(MealOffering.name == "Rollback Meal")).first() is None
