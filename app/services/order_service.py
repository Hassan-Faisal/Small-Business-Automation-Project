from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import setup_logger
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate
from app.services.tiffin_service import BULK_ORDER_THRESHOLD, SUPPORTED_PAYMENT_METHODS, TiffinPolicyService

logger = setup_logger(__name__)


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def _generate_order_number(self) -> str:
        return f"ORD-{uuid4().hex[:12].upper()}"

    def _load_order(self, order_number: str) -> Order | None:
        stmt = select(Order).where(Order.order_number == order_number).options(selectinload(Order.items).selectinload(OrderItem.product))
        return self.db.scalars(stmt).first()

    def create_draft_order(self, payload: OrderCreate) -> Order:
        try:
            if payload.payment_method is not None and payload.payment_method not in SUPPORTED_PAYMENT_METHODS:
                raise ValueError("Unsupported payment method.")
            if payload.is_bulk_order and payload.requested_delivery_at is not None and payload.number_of_boxes is not None:
                bulk_result = TiffinPolicyService(self.db).validate_bulk_order(requested_delivery_at=payload.requested_delivery_at, number_of_boxes=payload.number_of_boxes, threshold=BULK_ORDER_THRESHOLD)
                if not bulk_result.is_valid:
                    raise ValueError(bulk_result.reason or "Bulk order validation failed.")
            order = Order(order_number=payload.order_number or self._generate_order_number(), customer_phone=payload.customer_phone.strip(), delivery_address=payload.delivery_address.strip(), status="draft", total_amount=Decimal("0.00"), payment_method=payload.payment_method, is_bulk_order=payload.is_bulk_order, requested_delivery_at=payload.requested_delivery_at, number_of_boxes=payload.number_of_boxes, special_instructions=payload.special_instructions)
            self.db.add(order)
            self.db.flush()
            total = Decimal("0.00")
            items: list[OrderItem] = []
            for item in payload.items:
                if item.quantity <= 0:
                    raise ValueError("Quantity must be greater than zero.")
                product = self.db.get(Product, item.product_id)
                if product is None:
                    raise ValueError(f"Product {item.product_id} not found.")
                if not product.is_available:
                    raise ValueError(f"Product {product.id} is not available.")
                subtotal = product.price * item.quantity
                total += subtotal
                items.append(OrderItem(order_id=order.id, product_id=product.id, quantity=item.quantity, unit_price=product.price, subtotal=subtotal))
            if not items:
                raise ValueError("Cannot create an empty order.")
            self.db.add_all(items)
            order.total_amount = total
            self.db.commit()
            self.db.refresh(order)
            logger.info("order_created", extra={"event": "order_created", "order_number": order.order_number, "item_count": len(items), "total_amount": str(total)})
            return self.retrieve_order_by_order_number(order.order_number) or order
        except Exception:
            self.db.rollback()
            raise

    def confirm_order(self, order_number: str) -> Order:
        try:
            order = self._load_order(order_number)
            if order is None:
                raise ValueError(f"Order {order_number} not found.")
            if order.status == "confirmed":
                raise ValueError(f"Order {order_number} is already confirmed.")
            if order.status in {"cancelled", "completed"}:
                raise ValueError(f"Order {order_number} cannot be confirmed from status {order.status}.")
            if not order.items:
                raise ValueError("Cannot confirm an empty order.")
            order.status = "confirmed"
            order.confirmed_at = datetime.now(timezone.utc)
            self.db.commit()
            return self.retrieve_order_by_order_number(order_number) or order
        except Exception:
            self.db.rollback()
            raise

    def cancel_order(self, order_number: str) -> Order:
        try:
            order = self._load_order(order_number)
            if order is None:
                raise ValueError(f"Order {order_number} was not found.")
            if order.status == "cancelled":
                raise ValueError(f"Order {order_number} is already cancelled.")
            if order.status == "completed":
                raise ValueError(f"Order {order_number} has already been completed and cannot be cancelled.")
            order.status = "cancelled"
            order.cancelled_at = datetime.now(timezone.utc)
            self.db.commit()
            return self.retrieve_order_by_order_number(order_number) or order
        except Exception:
            self.db.rollback()
            raise

    def retrieve_order_by_order_number(self, order_number: str) -> Order | None:
        return self._load_order(order_number)

    def update_order_status(self, order_number: str, status: str) -> Order:
        try:
            order = self._load_order(order_number)
            if order is None:
                raise ValueError(f"Order {order_number} not found.")
            order.status = status
            self.db.commit()
            loaded = self.retrieve_order_by_order_number(order_number)
            if loaded is None:
                raise ValueError(f"Order {order_number} not found after update.")
            return loaded
        except Exception:
            self.db.rollback()
            raise


