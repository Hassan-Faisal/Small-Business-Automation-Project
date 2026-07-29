from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate
from app.services.order_service import OrderService
from app.services.product_service import ProductService


def normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def build_menu_items(products: list[Product]) -> list[dict[str, Any]]:
    return [
        {"id": product.id, "name": product.name, "price": str(product.price)}
        for product in products
    ]


def add_item_to_cart(cart: list[dict[str, object]], product: Product, quantity: int) -> list[dict[str, object]]:
    updated = [item for item in cart if item.get("product_id") != product.id]
    updated.append({"product_id": product.id, "name": product.name, "quantity": quantity, "unit_price": str(product.price)})
    return updated


def remove_item_from_cart(cart: list[dict[str, object]], product_id: int) -> list[dict[str, object]]:
    return [item for item in cart if item.get("product_id") != product_id]


def calculate_cart_total(cart: list[dict[str, object]]) -> Decimal:
    total = Decimal("0.00")
    for item in cart:
        unit_price = Decimal(str(item["unit_price"]))
        quantity = int(item["quantity"])
        total += unit_price * quantity
    return total


def create_order_payload(order_number: str, customer_phone: str, address: str, cart: list[dict[str, object]]) -> OrderCreate:
    items = [
        {"product_id": int(item["product_id"]), "quantity": int(item["quantity"])}
        for item in cart
    ]
    return OrderCreate(
        order_number=order_number,
        customer_phone=customer_phone,
        delivery_address=address,
        items=items,
    )


def summarize_order(order: Order) -> dict[str, Any]:
    return {
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": str(order.total_amount),
        "items": [
            {"name": item.product.name, "quantity": item.quantity, "unit_price": str(item.unit_price), "subtotal": str(item.subtotal)}
            for item in order.items
        ],
    }
