from __future__ import annotations

import importlib
import os
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.api.routes.orders import get_order_service
from app.api.routes.products import get_product_service
from app.core.database import Base
from app.dependencies.database import get_db
from app.main import app
from app.schemas.order import OrderCreate
from app.schemas.product import ProductCreate
from app.services.order_service import OrderService
from app.services.product_service import ProductService


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "api.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_product_service] = lambda: ProductService(next(override_get_db()))
    app.dependency_overrides[get_order_service] = lambda: OrderService(next(override_get_db()))

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_settings_use_safe_defaults_when_environment_is_missing(monkeypatch, tmp_path):
    for key in [
        "APP_NAME",
        "APP_VERSION",
        "APP_DESCRIPTION",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_EMBEDDING_MODEL",
        "DATABASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)

    import app.core.config as config_module

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.APP_NAME == "WhatsApp AI Assistant"
    assert reloaded.settings.APP_VERSION in {"0.1.0", "1.0.0"}
    assert reloaded.settings.APP_DESCRIPTION in {"WhatsApp-first AI ordering assistant", "An AI-powered WhatsApp Business Assistant built with FastAPI and LangGraph."}
    assert reloaded.settings.DATABASE_URL.startswith("sqlite://")
    assert "business.db" in reloaded.settings.DATABASE_URL


def test_sqlite_database_url_is_normalized_from_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    import app.core.config as config_module

    reloaded = importlib.reload(config_module)
    database_path = Path(reloaded.settings.DATABASE_URL.removeprefix("sqlite:///"))

    assert database_path.is_absolute()
    assert database_path.name == "test.db"


def test_product_routes(client):
    create_response = client.post(
        "/products",
        json={
            "name": "Burger",
            "description": "Classic",
            "price": "10.00",
            "is_available": True,
        },
    )
    assert create_response.status_code == 201
    product = create_response.json()
    assert product["name"] == "Burger"

    list_response = client.get("/products")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/products/{product['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Burger"

    patch_response = client.patch(
        f"/products/{product['id']}",
        json={"is_available": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["is_available"] is False

    assert client.get("/products").json() == []


def test_order_routes(client):
    product = client.post(
        "/products",
        json={
            "name": "Pizza",
            "description": "Large",
            "price": "15.00",
            "is_available": True,
        },
    ).json()

    order_response = client.post(
        "/orders",
        json={
            "order_number": "ORD-1001",
            "customer_phone": "+123456789",
            "delivery_address": "123 Main St",
            "items": [{"product_id": product["id"], "quantity": 2}],
        },
    )
    assert order_response.status_code == 201
    order = order_response.json()
    assert order["status"] == "draft"
    assert order["total_amount"] == "30.00"
    assert order["items"][0]["unit_price"] == "15.00"
    assert order["items"][0]["subtotal"] == "30.00"

    get_response = client.get("/orders/ORD-1001")
    assert get_response.status_code == 200
    assert get_response.json()["order_number"] == "ORD-1001"

    confirm_response = client.post("/orders/ORD-1001/confirm")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"

    duplicate_response = client.post("/orders/ORD-1001/confirm")
    assert duplicate_response.status_code == 409

    status_response = client.patch(
        "/orders/ORD-1001/status",
        json={"status": "delivered"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "delivered"


def test_route_validation_and_not_found(client):
    not_found = client.get("/products/9999")
    assert not_found.status_code == 404

    invalid = client.post(
        "/products",
        json={
            "name": "Soup",
            "description": "Hot",
            "price": "-1.00",
            "is_available": True,
        },
    )
    assert invalid.status_code == 422

